import tensorflow as tf
from os import path

from tensorflow.contrib.slim.python.slim.nets.inception_v3 import inception_v3_base

from utlis import call_program, working_dir

slim = tf.contrib.slim


class Inception:
    def __init__(self, cache_dir, url, tar, model_file):
        self.url = url
        self.cache_dir = path.abspath(cache_dir)
        self.model_file = model_file
        self.tar = tar
        self._model_path = path.join(self.cache_dir, model_file)

    @staticmethod
    def inception_v3(images,
                     trainable=True,
                     is_training=True,
                     weight_decay=0.00004,
                     stddev=0.1,
                     dropout_keep_prob=0.8,
                     use_batch_norm=True,
                     batch_norm_params=None,
                     add_summaries=True,
                     scope="InceptionV3"):
        """Builds an Inception V3 subgraph for image embeddings.

      Args:
        images: A float32 Tensor of shape [batch, height, width, channels].
        trainable: Whether the inception submodel should be trainable or not.
        is_training: Boolean indicating training mode or not.
        weight_decay: Coefficient for weight regularization.
        stddev: The standard deviation of the trunctated normal weight initializer.
        dropout_keep_prob: Dropout keep probability.
        use_batch_norm: Whether to use batch normalization.
        batch_norm_params: Parameters for batch normalization. See
          tf.contrib.layers.batch_norm for details.
        add_summaries: Whether to add activation summaries.
        scope: Optional Variable scope.

      Returns:
        end_points: A dictionary of activations from inception_v3 layers.
      """
        # Only consider the inception model to be in training mode if it's trainable.
        is_inception_model_training = trainable and is_training

        if use_batch_norm:
            # Default parameters for batch normalization.
            if not batch_norm_params:
                batch_norm_params = {
                    "is_training": is_inception_model_training,
                    "trainable": trainable,
                    # Decay for the moving averages.
                    "decay": 0.9997,
                    # Epsilon to prevent 0s in variance.
                    "epsilon": 0.001,
                    # Collection containing the moving mean and moving variance.
                    "variables_collections": {
                        "beta": None,
                        "gamma": None,
                        "moving_mean": ["moving_vars"],
                        "moving_variance": ["moving_vars"],
                    }
                }
        else:
            batch_norm_params = None

        if trainable:
            weights_regularizer = tf.contrib.layers.l2_regularizer(weight_decay)
        else:
            weights_regularizer = None

        with tf.variable_scope(scope, "InceptionV3", [images]) as scope:
            with slim.arg_scope(
                    [slim.conv2d, slim.fully_connected],
                    weights_regularizer=weights_regularizer,
                    trainable=trainable):
                with slim.arg_scope(
                        [slim.conv2d],
                        weights_initializer=tf.truncated_normal_initializer(stddev=stddev),
                        activation_fn=tf.nn.relu,
                        normalizer_fn=slim.batch_norm,
                        normalizer_params=batch_norm_params):
                    net, end_points = inception_v3_base(images, scope=scope)
                    with tf.variable_scope("logits"):
                        shape = net.get_shape()
                        net = slim.avg_pool2d(net, shape[1:3], padding="VALID", scope="pool")
                        net = slim.dropout(
                            net,
                            keep_prob=dropout_keep_prob,
                            is_training=is_inception_model_training,
                            scope="dropout")
                        net = slim.flatten(net, scope="flatten")

        # Add summaries.
        if add_summaries:
            for v in end_points.values():
                tf.contrib.layers.summaries.summarize_activation(v)

        return net

    @property
    def model_path(self):
        if not path.isfile(self._model_path):
            with working_dir(self.cache_dir):
                call_program(['wget', '-nc', self.url])
                call_program(['tar', '-xvf', self.tar, '-C', './'])
        return self._model_path

    def load(self, sess):
        saver = tf.train.Saver(tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope="InceptionV3"))
        saver.restore(sess, self.model_path)

    def build(self, images, mode, trainable, **kwargs):
        return self.inception_v3(images, trainable=trainable, is_training=tf.estimator.ModeKeys.TRAIN == mode,
                                 **kwargs),



# def test_input_fn():
#     import image_processing
#     import urllib.request
#     import tensorflow.tf.data as tfdata
#     import image_embedding
#
#     if args.test_urls:
#         jpegs = [urllib.request.urlopen(url).read()
#                  for url in args.test_urls.split(',')]
#
#         with tf.Graph().as_default() as g:
#             jpeg = tf.placeholder(dtype=tf.string)
#
#             image = image_processing.process_image(jpeg, False)
#
#             features = image_embedding.inception_v3([image], False, False)
#
#             saver = tf.train.Saver(tf.get_collection(
#                 tf.GraphKeys.GLOBAL_VARIABLES, scope="InceptionV3"))
#             with tf.Session(graph=g) as sess:
#                 saver.restore(sess, args.cnn_model)
#                 features_list = [sess.run(features, feed_dict={jpeg: j}) for j in jpegs]
#
#         dataset = tfdata.Dataset.from_tensor_slices(np.array(features_list))
#
#         return {'features': dataset.make_one_shot_iterator().get_next()}, None
#     else:
#         raise Exception('pass test_urls')