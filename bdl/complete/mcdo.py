import tensorflow as tf
from tensorflow.distributions import Normal
import numpy as np
import matplotlib.pyplot as plt
import os
import argparse
import time

from layers import dense

os.environ['CUDA_VISIBLE_DEVICES'] = '0'

# generate data
def func(x, noise=0.03):
    eps = noise * np.random.randn(*x.shape)
    return x + eps + np.sin(4*(x + eps)) + np.sin(13*(x + eps))

np.random.seed(42)
x_train_np = np.concatenate([
    0.6*np.random.rand(10),
    0.8 + 0.2*np.random.rand(5)])[...,None]
y_train_np = func(x_train_np, noise=0.03)

x_test_np = np.concatenate([
    0.6*np.random.rand(5),
    0.8 + 0.2*np.random.rand(2)])[...,None]
y_test_np = func(x_test_np, noise=0.03)
np.random.seed(int(time.time()))

x = tf.placeholder(tf.float32, shape=[None, 1])
y = tf.placeholder(tf.float32, shape=[None, 1])

# define network
out = dense(x, 64, name='dense1')
out = tf.nn.relu(tf.nn.dropout(out, rate=0.2))
out = dense(out, 64, name='dense2')
out = tf.nn.relu(tf.nn.dropout(out, rate=0.2))
out = dense(out, 2, name='dense3')
mu, sigma = tf.split(out, 2, axis=-1)
sigma = 0.1 + 0.9 * tf.nn.softplus(sigma)

parser = argparse.ArgumentParser()
parser.add_argument('--lr', type=float, default=1e-2)
parser.add_argument('--num_steps', type=int, default=10000)
parser.add_argument('--test', action='store_true')
parser.add_argument('--wd', type=float, default=1e-4)
parser.add_argument('--num_samples', type=int, default=30)
args = parser.parse_args()

if not args.test:
    if not os.path.isdir('results/mcdo'):
        os.makedirs('results/mcdo')

    # training objective
    ll = tf.reduce_mean(Normal(mu, sigma).log_prob(y))

    # weight decay
    wd = args.wd * tf.add_n([tf.nn.l2_loss(var) for var in tf.trainable_variables()])

    saver = tf.train.Saver(tf.trainable_variables())
    train_op = tf.train.AdamOptimizer(args.lr).minimize(-ll + wd)

    # training loop
    sess = tf.Session()
    sess.run(tf.global_variables_initializer())

    for t in range(args.num_steps):
        sess.run(train_op, {x:x_train_np, y:y_train_np})

        if (t+1)% 100 == 0:
            train_ll = sess.run(ll, {x:x_train_np, y:y_train_np})
            test_ll = sess.run(ll, {x:x_test_np, y:y_test_np})

            print('step %d train ll %.4f test ll %.4f' % (t+1, train_ll, test_ll))
            saver.save(sess, os.path.join('results/mcdo', 'model'))

    saver.save(sess, os.path.join('results/mcdo', 'model'))

else:
    sess = tf.Session()
    saver = tf.train.Saver(tf.trainable_variables())
    saver.restore(sess, os.path.join('results/mcdo', 'model'))

    x_np = np.linspace(-0.5, 1.5, 100)[...,None]
    y_true_np = func(x_np, noise=0.0)

    mu_np_list, sigma_np_list = [], []
    for i in range(args.num_samples):
        mu_np, sigma_np = sess.run([mu, sigma], {x:x_np})
        mu_np, sigma_np = mu_np.squeeze(), sigma_np.squeeze()
        mu_np_list.append(mu_np)
        sigma_np_list.append(sigma_np)

    mu_np = np.stack(mu_np_list)
    sigma_np = np.stack(sigma_np_list)
    sigma_np = np.sqrt((sigma_np**2).mean(0) + (mu_np**2).mean(0) - (mu_np.mean(0)**2))
    mu_np = mu_np.mean(0)

    x_np = x_np.squeeze()
    y_true_np = y_true_np.squeeze()
    x_train_np = x_train_np.squeeze()
    y_train_np = y_train_np.squeeze()

    plt.figure()
    plt.fill_between(x_np, mu_np-sigma_np, mu_np+sigma_np, alpha=0.3)
    plt.plot(x_np, mu_np, label='pred mean')
    plt.plot(x_train_np, y_train_np, 'r*', label='train')
    plt.plot(x_np, y_true_np, 'k--', label='true')
    plt.legend()
    plt.show()
