import tensorflow as tf
import tensorflow.contrib as contrib


def seq_loss(targets, logits, mask):
    with tf.variable_scope('seq_loss'):
        weights = tf.to_float(tf.reshape(mask, [-1]))
        losses = tf.nn.sparse_softmax_cross_entropy_with_logits(labels=tf.reshape(targets, [-1]),
                                                                logits=logits)
        batch_loss = tf.div(tf.reduce_sum(tf.multiply(losses, weights)),
                            tf.reduce_sum(weights),
                            name="batch_loss")
        tf.losses.add_loss(batch_loss)

        total_loss = tf.losses.get_total_loss()

        return total_loss, losses


def optimize_loss(total_loss,
                  initial_learning_rate,
                  num_examples_per_epoch,
                  num_epochs_per_decay,
                  learning_rate_decay_factor,
                  clip_gradients,
                  batch_size,
                  optimizer,
                  summaries):
    with tf.variable_scope('learning_rate'):
        learning_rate = tf.constant(initial_learning_rate)
        learning_rate_decay_fn = None
        if learning_rate_decay_factor > 0:
            num_batches_per_epoch = (num_examples_per_epoch / batch_size)
            decay_steps = int(num_batches_per_epoch *
                              num_epochs_per_decay)
            global_step = tf.train.get_or_create_global_step()
            epoch = tf.to_int32(tf.div(tf.to_float(global_step, name='float_global_step'),
                                       num_batches_per_epoch, name='float_epoch'), name='int_epoch')
            if summaries and 'epoch' in summaries:
                tf.summary.scalar('epoch', epoch)
                summaries.remove('epoch')

            def learning_rate_decay_fn(lr, global_step):
                return tf.train.exponential_decay(
                    lr,
                    global_step,
                    decay_steps=decay_steps,
                    decay_rate=learning_rate_decay_factor,
                    staircase=True)

    return contrib.layers.optimize_loss(
        loss=total_loss,
        global_step=tf.train.get_global_step(),
        learning_rate=learning_rate,
        optimizer=optimizer,
        clip_gradients=clip_gradients,
        summaries=summaries,
        learning_rate_decay_fn=learning_rate_decay_fn)
