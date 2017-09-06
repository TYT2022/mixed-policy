# While training is taking place, statistics on agent performance are available from Tensorboard. To launch it use:
# 
#   tensorboard --logdir=worker_0:'./train_0',worker_1:'./train_1',worker_2:'./train_2',worker_3:'./train_3'
#   tensorboard --logdir=worker_0:'./train_0'
#   tensorboard --logdir=worker_0:'./train_0',worker_1:'./train_1',worker_2:'./train_2',worker_3:'./train_3',worker_4:'./train_4',worker_5:'./train_5',worker_6:'./train_6',worker_7:'./train_7',worker_8:'./train_8',worker_9:'./train_9',worker_10:'./train_10',worker_11:'./train_11'


import argparse
import os
import threading
from time import sleep

import tensorflow as tf

from asyncdqn.QNetwork1step import QNetwork1Step
from asyncdqn.QNetworkPolicy import QNetworkPolicy
from asyncdqn.QNetworkPolicySlow import QNetworkPolicySlow
from asyncdqn.Slave import Worker
from asyncdqn.SlaveRPS import WorkerRPS
from asyncdqn.SlaveRandomRPS import WorkerRandomRPS
from simulator.GymPursuit import GymPursuit
from simulator.GymRPS import GymRPS
from simulator.GymRandomRPS import GymRandomRPS

max_episode_length = 2000
gamma = .9  # discount rate for advantage estimation and reward discounting
#Pursuit
#width = 15  # 84
#height = 15
#s_size = width * height  # Observations are greyscale frames of 84 * 84 * 1
#a_size = 5  # Agent can move Left, Right, up down, or nothing
# coins
width = 1  # 84
height = 1
s_size = 1  # Observations are greyscale frames of 84 * 84 * 1
a_size = 2  # Agent can move Left, Right, up down, or nothing
#randomRPS
width = 5
height = 5
s_size = width*height  # Observations are greyscale frames of 84 * 84 * 1
a_size = 4  # Agent can move Left, Right, up down, or nothing
load_model = False
model_path = './model'
debug = False
use_lstm = False
use_conv_layers = False
save_gifs = False
number_of_cell_types = 1 #3

parser = argparse.ArgumentParser()
parser.register("type", "bool", lambda v: v.lower() == "true")
parser.add_argument(
    "--num_slaves",
    type=int,
    default=3,
    help="Set number of available CPU threads"
)
parser.add_argument(
    "--num_predators",
    type=int,
    default=1,
    help="Set number of predators"
)
parser.add_argument(
    "--num_prey",
    type=int,
    default=1,
    help="Set number of prey"
)
parser.add_argument(
    "--alg",
    type=int,
    default=4,
    help="Which algorithm it is"
)
FLAGS, unparsed = parser.parse_known_args()

number_of_predators = FLAGS.num_predators
number_of_prey = FLAGS.num_prey

tf.reset_default_graph()

# Create a directory to save models and episode playback gifs
if not os.path.exists(model_path):
    os.makedirs(model_path)
if not os.path.exists('./frames'):
    os.makedirs('./frames')

with tf.device("/cpu:0"):
    global_episodes = tf.Variable(0, dtype=tf.int32, name='global_episodes', trainable=False)
    trainer_predator = tf.train.AdamOptimizer(learning_rate=1e-4)  # todo this was 1e-5 as of 02/05/2017
    trainer_prey = tf.train.AdamOptimizer(learning_rate=1e-4)  # todo this was 1e-5 as of 02/05/2017
    if FLAGS.alg in [3, 4, 5]:
        master_network_predator = QNetworkPolicy(s_size, a_size, 'global_predator', None, use_conv_layers, use_lstm,
                                                 width, height, number_of_cell_types)  # Generate global network
        master_network_prey = QNetworkPolicy(s_size, a_size, 'global_prey', None, use_conv_layers, use_lstm,
                                             width, height, number_of_cell_types)  # Generate global network
    elif FLAGS.alg in [1, 2]:
        master_network_predator = QNetworkPolicySlow(s_size, a_size, 'global_predator', None, use_conv_layers, use_lstm,
                                                 width, height, number_of_cell_types)  # Generate global network
        master_network_prey = QNetworkPolicySlow(s_size, a_size, 'global_prey', None, use_conv_layers, use_lstm,
                                             width, height, number_of_cell_types)  # Generate global network
    else:
        master_network_predator = QNetwork1Step(s_size, a_size, 'global_predator', None, use_conv_layers, use_lstm,
                                                 width, height, number_of_cell_types)  # Generate global network
        master_network_prey = QNetwork1Step(s_size, a_size, 'global_prey', None, use_conv_layers, use_lstm,
                                             width, height, number_of_cell_types)  # Generate global network
    workers = []
    # Create worker classes
    for i in range(FLAGS.num_slaves):
        if FLAGS.alg in [0, 1, 2, 3, 4, 5]: #todo - we're including alg 0 to have greedy dqn as well
            workers.append(WorkerRandomRPS(GymRandomRPS(2, width, width, debug), #GymRPS(numberOfActions=a_size), #
                              i, s_size, a_size, trainer_predator, trainer_prey, model_path, global_episodes,
                              width, height, number_of_cell_types, use_lstm, use_conv_layers, save_gifs,
                              number_of_predators, number_of_prey, FLAGS.alg))
        else:
            workers.append(Worker(GymPursuit(number_of_predators, number_of_prey, width, width, debug),
                          i, s_size, a_size, trainer_predator, trainer_prey, model_path, global_episodes,
                          width, height, number_of_cell_types, use_lstm, use_conv_layers, save_gifs,
                          number_of_predators, number_of_prey))
    saver = tf.train.Saver()

with tf.Session() as sess:
    coord = tf.train.Coordinator()
    if load_model:
        print('Loading Model...')
        ckpt = tf.train.get_checkpoint_state(model_path)
        saver.restore(sess, ckpt.model_checkpoint_path)
    else:
        sess.run(tf.global_variables_initializer())

    # This is where the asynchronous magic happens.
    # Start the "work" process for each worker in a separate threat.
    worker_threads = []
    for worker in workers:
        worker_work = lambda: worker.work(max_episode_length, gamma, sess, coord, saver)
        t = threading.Thread(target=(worker_work))
        t.start()
        sleep(0.5)

        worker_threads.append(t)

    coord.join(worker_threads)

print("Done")
with open("policy"+str(FLAGS.task_index)+".txt", "a") as myfile:
    myfile.write(str(FLAGS)+" "+str(workers[0].policy_evolution)+'\n')
