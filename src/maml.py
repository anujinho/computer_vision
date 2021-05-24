import argparse

import learn2learn as l2l
import numpy as np
import torch
import tqdm
from learn2learn.algorithms import maml
from torch import nn, optim

from src.zoo.maml_utils import inner_adapt_maml, setup
from src.utils import Profiler
from src.config import maml_omniglot, maml_mini

##############
# Parameters #
##############
parser = argparse.ArgumentParser()
parser.add_argument('--dataset', type=str)
parser.add_argument('--root', type=str)
parser.add_argument('--n-ways', type=int)
parser.add_argument('--k-shots', type=int)
parser.add_argument('--q-shots', type=int)
parser.add_argument('--inner-adapt-steps', type=int)
parser.add_argument('--inner-lr', type=float)
parser.add_argument('--meta-lr', type=float)
parser.add_argument('--meta-batch-size', type=int)
parser.add_argument('--iterations', type=int)
parser.add_argument('--order', type=bool)
parser.add_argument('--device', type=str)

args = parser.parse_args()

# Generating Tasks, initializing learners, loss, meta - optimizer
train_tasks, valid_tasks, test_tasks, learner = setup(
    args.dataset, args.root, args.n_ways, args.k_shots, args.q_shots, args.order, args.inner_lr, args.device)
opt = optim.Adam(learner.parameters(), args.meta_lr)
loss = nn.CrossEntropyLoss(reduction='mean')
profiler = Profiler('MAML_{}_{}-shot_{}-way_{}-queries'.format(args.dataset, args.n_ways, args.k_shots, args.q_shots))

## Training ##
for iter in tqdm.tqdm(range(args.iterations)):
    opt.zero_grad()
    meta_train_loss = []
    meta_valid_loss = []
    meta_train_acc = []
    meta_valid_acc = []

    for batch in range(args.meta_batch_size):
        ttask = train_tasks.sample()
        model = learner.clone()
        evaluation_loss, evaluation_accuracy = inner_adapt_maml(
            ttask, loss, model, args.n_ways, args.k_shots, args.q_shots, args.inner_adapt_steps, args.device)
        evaluation_loss.backward()
        meta_train_loss.append(evaluation_loss.item())
        meta_train_acc.append(evaluation_accuracy.item())

    vtask = valid_tasks.sample()
    model = learner.clone()
    validation_loss, validation_accuracy = inner_adapt_maml(
        vtask, loss, model, args.n_ways, args.k_shots, args.q_shots, args.inner_adapt_steps, args.device)
    meta_valid_loss.append(validation_loss.item())
    meta_valid_acc.append(validation_accuracy.item())

    profiler.log(np.array(meta_train_acc).mean(), np.array(meta_train_acc).std(), np.array(meta_train_loss).mean(), np.array(meta_train_loss).std(), np.array(
            meta_valid_acc).mean(), np.array(
            meta_valid_acc).std(), np.array(
            meta_valid_loss).mean(), np.array(
            meta_valid_loss).std())

    if (iter%500 == 0):
        print('Meta Train Accuracy: {:.4f} +- {:.4f}'.format(np.array(meta_train_acc).mean(), np.array(meta_train_acc).std()))
        print('Meta Valid Accuracy: {:.4f} +- {:.4f}'.format(np.array(meta_valid_acc).mean(), np.array(meta_valid_acc).std()))

    for p in learner.parameters():
        p.grad.data.mul_(1.0 / args.meta_batch_size)
    opt.step()

torch.save(learner, f='../repro')

## Testing ##
print('Testing on held out classes')
for batch in range(args.meta_batch_size):
    meta_test_acc = []
    meta_test_loss = []
    model = learner.clone()
    tetask = test_tasks.sample()
    evaluation_loss, evaluation_accuracy = inner_adapt_maml(
        tetask, loss, model, args.n_ways, args.k_shots, args.q_shots, args.inner_adapt_steps, args.device)
    meta_test_loss.append(evaluation_loss.item())
    meta_test_acc.append(evaluation_accuracy.item())
    print('Meta Test Accuracy', np.array(meta_test_acc).mean(), '+-', np.np.array(meta_test_acc).std())
    
