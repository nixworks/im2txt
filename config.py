import mscoco
from inception_fe import Inception
from faster_rcnn_inception_v2_fe import FasterRCNNInceptionV2
import beam_search
import train_utils
import train_eval_inputs
from functools import partial

import feature2seq


keep_checkpoint_max = 10
max_train_epochs = 500
save_checkpoints_steps = 1000
train_log_step_count_steps = 500
eval_log_step_count_steps = 50

batch_size = 1024
initial_learning_rate = 4.0
learning_rate_decay_factor = 0.35
num_epochs_per_decay = 20.0
optimizer = 'Adagrad'
clip_gradients = 5.0
seq_max_len = 100
beam_size = 1
num_lstm_units = 512

initializer_scale = 0.08
embedding_size = 512
lstm_dropout_keep_prob = 0.7

data_dir = 'data'

# Dataset

train_dataset = mscoco.MSCoco(cache_dir=data_dir,
                              images_gs_url='gs://images.cocodataset.org/train2014',
                              annotations_gs_url='gs://images.cocodataset.org/annotations',
                              caption_json_path='annotations/captions_train2014.json',
                              annotations_zip='annotations/annotations_trainval2014.zip',
                              image_dir='train2014')

eval_dataset = mscoco.MSCoco(cache_dir=data_dir,
                             images_gs_url='gs://images.cocodataset.org/val2014',
                             annotations_gs_url='gs://images.cocodataset.org/annotations',
                             caption_json_path='annotations/captions_val2014.json',
                             annotations_zip='annotations/annotations_trainval2014.zip',
                             image_dir='val2014')

num_examples_per_train_epoch = train_dataset.captions_dataset_length

num_examples_per_eval = eval_dataset.captions_dataset_length

caption_vocabulary = train_dataset.vocabulary

vocab_size = len(caption_vocabulary)

# Feature extractor

feature_detector = Inception(cache_dir=data_dir,
                             url='http://download.tensorflow.org/models/inception_v3_2016_08_28.tar.gz',
                             tar='inception_v3_2016_08_28.tar.gz',
                             model_file='inception_v3.ckpt')

# feature_detector = FasterRCNNInceptionV2(cache_dir=data_dir,
#                                          url='http://download.tensorflow.org/models/object_detection'
#                                              '/faster_rcnn_inception_v2_coco_2017_11_08.tar.gz',
#                                          tar='faster_rcnn_inception_v2_coco_2017_11_08.tar.gz',
#                                          model_file='faster_rcnn_inception_v2_coco_2017_11_08')

eval_input_fn = partial(train_eval_inputs.input_fn,
                        dataset=eval_dataset,
                        feature_extractor=feature_detector,
                        is_training=False,
                        cache_dir=eval_dataset.records_dir,
                        batch_size=batch_size,
                        max_epochs=1000000)

train_input_fn = partial(train_eval_inputs.input_fn,
                         dataset=train_dataset,
                         feature_extractor=feature_detector,
                         is_training=True,
                         cache_dir=train_dataset.records_dir,
                         batch_size=batch_size,
                         max_epochs=max_train_epochs)

predictor = partial(beam_search.beam_search,
                    beam_size=beam_size,
                    vocab_size=vocab_size,
                    start_word_index=caption_vocabulary.word_to_id(train_dataset.start_word),
                    end_word_index=caption_vocabulary.word_to_id(train_dataset.end_word),
                    seq_max_len=seq_max_len)

seq_generator = partial(feature2seq.feature2seq,
                        vocab_size=vocab_size,
                        predictor=predictor,
                        initializer_scale=initializer_scale,
                        embedding_size=embedding_size,
                        num_lstm_units=num_lstm_units,
                        lstm_dropout_keep_prob=lstm_dropout_keep_prob)

seq_loss = train_utils.seq_loss

optimize_loss = partial(train_utils.optimize_loss,
                        initial_learning_rate=initial_learning_rate,
                        num_examples_per_epoch=num_examples_per_train_epoch,
                        num_epochs_per_decay=num_epochs_per_decay,
                        learning_rate_decay_factor=learning_rate_decay_factor,
                        clip_gradients=clip_gradients,
                        batch_size=batch_size,
                        optimizer=optimizer,
                        summaries=[
                            "learning_rate",
                            "gradients",
                            "gradient_norm",
                            "global_gradient_norm",
                        ])


project_ignore = [data_dir]
