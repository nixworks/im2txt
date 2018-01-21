import mscoco
from inception_fe import Inception
from object_detector_fe import ObjectDetectorFE
import beam_search
import train_utils
import train_eval_inputs
from functools import partial
import tensorflow as tf
import image_processing
import feature2seq
import numpy as np

keep_checkpoint_max = 20
max_train_epochs = 500
save_checkpoints_steps = 1000
train_log_step_count_steps = 500
eval_log_step_count_steps = 50
eval_every_chackpoint = 5

batch_size = 1024
initial_learning_rate = 4.0
final_learning_rate = 0.02
decay_count = 6
learning_rate_decay_factor = 0.55
num_epochs_per_decay = max_train_epochs / (decay_count + 1)
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

num_examples_per_train_epoch = lambda: train_dataset.captions_dataset_length

num_examples_per_eval = lambda: eval_dataset.captions_dataset_length

caption_vocabulary = lambda: train_dataset.vocabulary

vocab_size = lambda: len(caption_vocabulary())


# Feature extractor

# feature_detector = Inception(cache_dir=data_dir,
#                              url='http://download.tensorflow.org/models/inception_v3_2016_08_28.tar.gz',
#                              tar='inception_v3_2016_08_28.tar.gz',
#                              model_file='inception_v3.ckpt')

def feature_selector():
    g = tf.get_default_graph()
    g.get_tensor_by_name('FeatureExtractor/MobilenetV1/Conv2d_13_pointwise_2_Conv2d_5_3x3_s2_128/Relu6')


def flat_tensor(t):
    return tf.reshape(t, [tf.shape(t)[0], -1])


feature_detector = ObjectDetectorFE(cache_dir=data_dir,
                                    url='http://download.tensorflow.org/models/object_detection/ssd_mobilenet_v1_coco_2017_11_17.tar.gz',
                                    tar='ssd_mobilenet_v1_coco_2017_11_17.tar.gz',
                                    model_file='ssd_mobilenet_v1_coco_2017_11_17/frozen_inference_graph.pb',
                                    feature_selector=lambda: tf.concat(
                                        [flat_tensor(tf.get_default_graph().get_tensor_by_name(n + ':0')) for n in [
                                            'FeatureExtractor/MobilenetV1/Conv2d_13_pointwise_2_Conv2d_5_3x3_s2_128/Relu6',
                                            'FeatureExtractor/MobilenetV1/Conv2d_13_pointwise_2_Conv2d_3_3x3_s2_256/Relu6'
                                        ]], axis=1, name='selected_features'),
                                    name='ssd_mobilenet_v1_coco_2017_11_17_fe_Conv2d_13_pointwise_2_Conv2d_3_3x3_s2_256_Conv2d_13_pointwise_2_Conv2d_5_3x3_s2_128')
image_size = 299

image_preprocessor = partial(image_processing.process_image,
                             height=image_size,
                             width=image_size,
                             image_format="jpeg")

def predictor(*args, **keywords):
    return beam_search.beam_search(*args, beam_size=beam_size,
                                   vocab_size=vocab_size(),
                                   start_word_index=caption_vocabulary().word_to_id(train_dataset.start_word),
                                   end_word_index=caption_vocabulary().word_to_id(train_dataset.end_word),
                                   seq_max_len=seq_max_len,
                                   **keywords)


def seq_output_constructor(pred, out_dic):
    for coef, ides in zip(pred['coefs'], np.transpose(pred['ides'])):
        out_dic['coefficient'] = float(coef)
        words = [caption_vocabulary().id_to_word(i) for i in ides]
        seq = []
        for w in words:
            if w == train_dataset.start_word and not len(seq):
                continue
            elif w == train_dataset.end_word or (len(seq) and w == train_dataset.start_word):
                break
            seq.append(w)

        out_dic['words'] = words
        out_dic['sequence'] = ' '.join(seq)


def output_constructor(pred, out_dic):
    seq_output_constructor(pred, out_dic)
    feature_detector.output_constructor(pred, out_dic)


def seq_generator(*args, **keywords):
    return feature2seq.feature2seq(*args,
                                   vocab_size=vocab_size(),
                                   predictor=predictor,
                                   initializer_scale=initializer_scale,
                                   embedding_size=embedding_size,
                                   num_lstm_units=num_lstm_units,
                                   lstm_dropout_keep_prob=lstm_dropout_keep_prob,
                                   **keywords)


seq_loss = train_utils.seq_loss


def optimize_loss(*args, **keywords):
    return train_utils.optimize_loss(*args,
                                     initial_learning_rate=initial_learning_rate,
                                     num_examples_per_epoch=num_examples_per_train_epoch(),
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
                                         "epoch"
                                     ],
                                     **keywords)


project_ignore = [data_dir]
