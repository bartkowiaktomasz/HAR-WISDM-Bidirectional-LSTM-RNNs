import numpy as np
import pandas as pd
import tensorflow as tf

from tensorflow.python.tools import inspect_checkpoint as chkp

# Display all variables
# chkp.print_tensors_in_checkpoint_file("model/classificator.ckpt", tensor_name='', all_tensors=True)

# Create the network
saver = tf.train.import_meta_graph("model/classificator.ckpt.meta")

# Load the parameters
with tf.Session() as sess:
    new_saver = tf.train.import_meta_graph("model/classificator.ckpt.meta")
    new_saver.restore(sess, tf.train.latest_checkpoint("model/"))


##################################################
### MAIN
##################################################
# if __name__ == '__main__':
