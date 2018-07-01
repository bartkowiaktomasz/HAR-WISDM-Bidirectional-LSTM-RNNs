import numpy as np
import pandas as pd
import tensorflow as tf
from scipy import stats
from sklearn import metrics
from sklearn.model_selection import train_test_split

import pickle

from tempfile import TemporaryFile

##################################################
### GLOBAL VARIABLES
##################################################
COLUMN_NAMES = [
    'user',
    'activity',
    'timestamp',
    'x-axis',
    'y-axis',
    'z-axis'
]

LABELS = [
    'Downstairs',
    'Jogging',
    'Sitting',
    'Standing',
    'Upstairs',
    'Walking'
]

DATA_PATH = 'data/WISDM_ar_v1.1_raw.txt'

RANDOM_SEED = 13

# Data preprocessing
TIME_STEP = 100

# Model
N_CLASSES = 6
N_FEATURES = 3  # x-acceleration, y-acceleration, z-acceleration

# Hyperparameters
N_LSTM_LAYERS = 2
N_EPOCHS = 30
L2_LOSS = 0.0015
LEARNING_RATE = 0.0025

# Hyperparameters optimized using BO
SEGMENT_TIME_SIZE = 180
N_HIDDEN_NEURONS = 30
BATCH_SIZE = 10

##################################################
### FUNCTIONS
##################################################

# Returns a tenforflow LSTM NN
# Input of shape (BATCH_SIZE, SEGMENT_TIME_SIZE, N_FEATURES)
def createBidirLSTM(X, SEGMENT_TIME_SIZE, N_HIDDEN_NEURONS):

    W = {
        'hidden': tf.Variable(tf.random_normal([N_FEATURES, 2*N_HIDDEN_NEURONS])),
        'output': tf.Variable(tf.random_normal([2*N_HIDDEN_NEURONS, N_CLASSES]))
    }

    b = {
        'hidden': tf.Variable(tf.random_normal([2*N_HIDDEN_NEURONS], mean=1.0)),
        'output': tf.Variable(tf.Variable(tf.random_normal([N_CLASSES])))
    }

    # Transpose and then reshape to 2D of size (BATCH_SIZE * SEGMENT_TIME_SIZE, N_FEATURES)
    X = tf.unstack(X, SEGMENT_TIME_SIZE, 1)

    # Stack two LSTM cells on top of each other
    lstm_fw_cell_1 = tf.contrib.rnn.BasicLSTMCell(N_HIDDEN_NEURONS, forget_bias=1.0)
    lstm_fw_cell_2 = tf.contrib.rnn.BasicLSTMCell(N_HIDDEN_NEURONS, forget_bias=1.0)
    lstm_bw_cell_1 = tf.contrib.rnn.BasicLSTMCell(N_HIDDEN_NEURONS, forget_bias=1.0)
    lstm_bw_cell_2 = tf.contrib.rnn.BasicLSTMCell(N_HIDDEN_NEURONS, forget_bias=1.0)

    outputs, _, _ = tf.contrib.rnn.stack_bidirectional_rnn([lstm_fw_cell_1, lstm_fw_cell_2], [lstm_bw_cell_1, lstm_bw_cell_2], X, dtype=tf.float32)

    # Get output for the last time step from a "many to one" architecture
    last_output = outputs[-1]
    return tf.matmul(last_output, W['output'] + b['output'])


def evaluate(data):

    # DATA PREPROCESSING
    data_convoluted = []
    labels = []

    # Slide a "SEGMENT_TIME_SIZE" wide window with a step size of "TIME_STEP"
    # print("SEGMENT_TIME_SIZE, N_HIDDEN_NEURONS, BATCH_SIZE: ", SEGMENT_TIME_SIZE, N_HIDDEN_NEURONS, BATCH_SIZE)
    for i in range(0, len(data) - SEGMENT_TIME_SIZE, TIME_STEP):
        x = data['x-axis'].values[i: i + SEGMENT_TIME_SIZE]
        y = data['y-axis'].values[i: i + SEGMENT_TIME_SIZE]
        z = data['z-axis'].values[i: i + SEGMENT_TIME_SIZE]
        data_convoluted.append([x, y, z])

        # Label for a data window is the label that appears most commonly
        label = stats.mode(data['activity'][i: i + SEGMENT_TIME_SIZE])[0][0]
        labels.append(label)

    # Convert to numpy
    data_convoluted = np.asarray(data_convoluted, dtype=np.float32).transpose(0, 2, 1)

    # One-hot encoding
    labels = np.asarray(pd.get_dummies(labels), dtype=np.float32)

    # SPLIT INTO TRAINING AND TEST SETS
    X_train, X_test, y_train, y_test = train_test_split(data_convoluted, labels, test_size=0.3, random_state=RANDOM_SEED)

    ##### BUILD A MODEL
    # Reset compuitational graph
    tf.reset_default_graph()

    # Placeholders
    X = tf.placeholder(tf.float32, [None, SEGMENT_TIME_SIZE, N_FEATURES], name="X")
    y = tf.placeholder(tf.float32, [None, N_CLASSES])

    y_pred = createBidirLSTM(X, SEGMENT_TIME_SIZE, N_HIDDEN_NEURONS)
    y_pred_softmax = tf.nn.softmax(y_pred)

    # LOSS
    l2 = L2_LOSS * sum(tf.nn.l2_loss(i) for i in tf.trainable_variables())
    loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits_v2(logits=y_pred, labels=y)) + l2

    # OPTIMIZER
    optimizer = tf.train.AdamOptimizer(learning_rate=LEARNING_RATE).minimize(loss)
    correct_pred = tf.equal(tf.argmax(y_pred_softmax, 1), tf.argmax(y, 1))
    accuracy = tf.reduce_mean(tf.cast(correct_pred, dtype=tf.float32))

    # TRAINING
    saver = tf.train.Saver()

    history = dict(train_loss=[], train_acc=[], test_loss=[], test_acc=[])
    sess = tf.InteractiveSession()
    sess.run(tf.global_variables_initializer())

    train_count = len(X_train)

    for i in range(1, N_EPOCHS + 1):
        for start, end in zip(range(0, train_count, BATCH_SIZE), range(BATCH_SIZE, train_count + 1, BATCH_SIZE)):
            sess.run(optimizer, feed_dict={X: X_train[start:end], y: y_train[start:end]})

            _, acc_train, loss_train = sess.run([y_pred_softmax, accuracy, loss], feed_dict={X: X_train, y: y_train})
            _, acc_test, loss_test = sess.run([y_pred_softmax, accuracy, loss], feed_dict={X: X_test, y: y_test})

            history['train_loss'].append(loss_train)
            history['train_acc'].append(acc_train)
            history['test_loss'].append(loss_test)
            history['test_acc'].append(acc_test)

            if(i % 5 != 0):
                continue

            print(f'epoch: {i} test accuracy: {acc_test} loss: {loss_test}')

    # Save the model
    saver.save(sess, "./classificator.ckpt")
    predictions, acc_final, loss_final = sess.run([y_pred_softmax, accuracy, loss], feed_dict={X: X_test, y: y_test})

    return acc_final

##################################################
### MAIN
##################################################
if __name__ == '__main__':

    # LOAD DATA
    data = pd.read_csv(DATA_PATH, header=None, names=COLUMN_NAMES)
    data['z-axis'].replace({';': ''}, regex=True, inplace=True)
    data = data.dropna()

    acc_final = evaluate(data)
    print("Final accuracy: ", acc_final)
