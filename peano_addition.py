"""
Generates data for the 'Peano addition' dataset, where we perform additions
according to the Peano axiom system, i.e. a number is defined as 0 or succ(n)
where n is a number, and the addition is defined recursively as
+(m, 0) = m and +(m, succ(n)) = +(succ(m), n).

This leads to the following rules to resolve additions.

1. +(m, 0) resolves to m, i.e. the + and the 0 are deleted.
2. +(m, succ(n)) resolves to +(succ(m), n), i.e. + inserts a succ as left
   child, and the right-hand-side succ is deleted.
3. +(m, n) resolves to +(m, succ(n-1)), i.e. + inserts a succ as right child
   and n is replaced with n-1.
4. succ(n) resolves to n+1 if succ is not the right child of a + operator.

A time series is generated by applying the rules until no rule matches anymore.

"""

# Copyright (C) 2020-2021
# Benjamin Paaßen
# The University of Sydney

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import torch
import numpy as np
from edist.alignment import Alignment
import edist.tree_edits as tree_edits
import edist.tree_utils as tree_utils
import pytorch_tree_edit_networks as ten

__author__ = 'Benjamin Paaßen'
__copyright__ = 'Copyright 2020-2021, Benjamin Paaßen'
__license__ = 'GPLv3'
__version__ = '1.0.0'
__maintainer__ = 'Benjamin Paaßen'
__email__  = 'bpaassen@techfak.uni-bielefeld.de'

alphabet = ['+', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'succ', 'root']

def generate_time_series(max_additions = 3, max_input = 9):
    """ Generates a random addition tree, which is then resolved using the
    Peano addition axioms.

    For more details, refer to the _generate_tree() and _simplify() method
    respectively.

    Parameters
    ----------
    max_additions: int (default = 3)
        The maximum number of addition operators in the generated tree. Note
        that the space of possible trees grows exponentially in this parameter.
        For the default value, already >30k trees are possible.
    max_input: int (default = 9)
        The maximum number permitted in the input tree. Note that numbers
        larger than 9 get set modulo 10 anyways.

    Returns
    -------
    time_series: list
        A list of trees with successively simpler versions of the initial
        addition expression until only a single number is left.

    """
    # generate a tree first
    nodes, adj = _generate_tree(max_additions, max_input)
    # and simplify it
    try:
        return _simplify(nodes, adj)
    except Exception as ex:
        print(tree_utils.tree_to_string(nodes, adj, indent = True, with_indices = True))
        raise ex

def _generate_tree(max_additions = 3, max_input = 3):
    """ Generates a random addition expression with at most max_additions
    addition operators.

    In more detail, the generation is done via a stochastic regular tree
    grammar with probability 0.55 for '+', and probability 0.05 for each number
    between 1 and 9 if not all + operators have been used that, and probability
    1. / 9. for all numbers between 1 and 9 otherwise.

    Parameters
    ----------
    max_additions: int (default = 3)
        The maximum number of addition operators in the generated tree. Note
        that the space of possible trees grows exponentially in this parameter.
        For the default values, already ~500 trees are possible.
    max_input: int (default = 3)
        The maximum number permitted in the input tree. Note that numbers
        larger than 9 get modulo 10 anyways. Also note that the space of
        possible trees grows with a polynomial to the power of max_additions
        in this parameter. For the default values, already ~500 trees are
        possible.

    Returns
    -------
    nodes: list
        The node list of the generated tree.
    adj: list
        The adjacency list of the generated tree.

    """

    if max_input < 1:
        raise ValueError('max_input must be a strictly positive integer but was %s' % str(max_input))
    if max_input > 9:
        max_input = max_input % 10

    prob_plus = np.zeros(max_input + 2)
    prob_non_plus = np.zeros(max_input + 2)
    prob_plus[0] = 0.5
    prob_plus[2:] = 1. / (2. * max_input)
    prob_non_plus[2:] = 1. / max_input

    # initialize node and adjacency list
    nodes = ['root']
    adj = [[]]

    # initialize a stack for generation which always contains the parent index
    stk = [0]
    while stk:
        # pop the current parent from the stack
        p = stk.pop()
        # sample a label for the new node with a probability distribution
        # dependent on the remaining binary operations and whether the parent
        # node is a 'not'
        if max_additions > 0:
            r = np.random.choice(len(prob_plus), 1, p = prob_plus)
        else:
            r = np.random.choice(len(prob_non_plus), 1, p = prob_non_plus)
        # append the new node to the tree
        i = len(nodes)
        label = alphabet[r[0]]
        nodes.append(label)
        adj.append([])
        adj[p].append(i)
        # push new entries on the stack, depending on the label
        if label == '+':
            stk.append(i)
            stk.append(i)
            max_additions -= 1
    # return the generated tree
    return nodes, adj

def _simplify(nodes, adj, verbose = False):
    """ Applies the Peano addition definition +(m, succ(n)) = succ(+(m,n)) with
    base case +(m, 0) = m until it can not be applied anymore.

    This leads to the following rules to resolve additions.

    1. +(m, 0) resolves to m, i.e. the + and the 0 are deleted.
    2. +(m, succ(n)) resolves to +(succ(m), n), i.e. + inserts a succ as left
       child, and the right-hand-side succ is deleted.
    3. +(m, n) resolves to +(m, succ(n-1)), i.e. + inserts a succ as right child
       and n is replaced with n-1.
    4. succ(n) resolves to n+1 if succ is not the right child of a + operator.

    which are all applied until no rule matches anymore.

    Parameters
    ----------
    nodes: list
        The node list of the tree to be simplified.
    adj: list
        The adjacency list of the tree to be simplified.

    Returns
    -------
    time_series: list
        A list of trees with successively simpler versions of the initial
        given tree, until the Peano addition definition can not be applied
        anymore.

    """
    # initialize the time series
    time_series = [(nodes, adj)]
    while True:
        if verbose:
            print('current tree: %s' % tree_utils.tree_to_string(nodes, adj, indent = True, with_indices = True))
        # retrieve the parent of each node
        pi = np.zeros(len(nodes), dtype=int)
        for i in range(len(nodes)):
            for j in adj[i]:
                pi[j] = i
        # initialize a new script
        script = tree_edits.Script()
        # maintain an array to keep track of the index shift
        index_shift = np.zeros(len(nodes), dtype=int)
        # iterate over the tree and look for remaining addition operators
        for i in range(len(nodes)):
            if nodes[i] == '+':
                # once we found an addition operator, check the right child
                right = adj[i][1]
                if nodes[right] == '0':
                    # if the right child is zero, we have reached our base case.
                    # remove the + operator and the zero.
                    script.append(tree_edits.Deletion(i + index_shift[i]))
                    index_shift[i+1:] -= 1
                    script.append(tree_edits.Deletion(right + index_shift[right]))
                    index_shift[right+1:] -= 1
                elif nodes[right] == 'succ':
                    # if the right child is succ, insert a new 'succ' as parent
                    # of the left child and delete the current 'succ'
                    script.append(tree_edits.Insertion(i + index_shift[i], 0, 'succ', 1))
                    index_shift[i+1:right+1] += 1
                    script.append(tree_edits.Deletion(right + index_shift[right]))
                elif nodes[right] != '+':
                    # if the right child is anything else, we need to re-write
                    # a number as the successor of another one, such that we
                    # can apply the previous rule in the next time step.
                    pred = str(int(nodes[right])-1)
                    script.append(tree_edits.Insertion(i + index_shift[i], 1, 'succ', 1))
                    index_shift[right:] += 1
                    script.append(tree_edits.Replacement(right + index_shift[right], pred))
            elif nodes[i] == 'succ' and (nodes[pi[i]] != '+' or pi[i] == i-1):
                # if we found a 'succ' operator which is not the right child of a
                # plus operator, we can try to resolve this succ operator
                child = adj[i][0]
                if nodes[child] not in ['succ', '+']:
                    script.append(tree_edits.Deletion(i + index_shift[i]))
                    index_shift[i+1:] -= 1
                    script.append(tree_edits.Replacement(child + index_shift[child], str((int(nodes[child])+1) % 10)))
        # check if we have changed anything this iteration
        if len(script) == 0:
            # if not, end the process
            break
        if verbose:
            print('script: %s' % str(script))
        # otherwise, append a new entry to the time series and continue
        nodes, adj = script.apply(nodes, adj)
        time_series.append((nodes, adj))
    return time_series

def compute_loss(model, time_series, verbose = False):
    """ A custom loss function for the Peano addition task using a protocol
    with only a single predictive step between graphs.

    Parameters
    ----------
    model: class pytorch_tree_edit_networks.TEN
        A tree edit network for which the loss shall be computed.
    time_series: list
        A list of trees as returned by _simplify.

    Returns
    -------
    loss: torch.tensor
        The graph edit network loss between the tree edit network predictions
        and the scores that ought to be generated.

    """
    # verify that the model does not expect memory
    if model._dim_memory > 0:
        raise ValueError('The peano_addition.compute_loss function is not compatible with a tree edit network with memory.')
    # initialize loss
    loss = torch.zeros(1)
    for t in range(len(time_series)):
        nodes, adj = time_series[t]
        # retrieve the parent of each node
        pi = np.zeros(len(nodes), dtype=int)
        for i in range(len(nodes)):
            for j in adj[i]:
                pi[j] = i
        # construct the initial node features for the current tree
        X = ten._degree_features(nodes, adj, model._dim_in_extra - 1, 0)
        # perform the prediction of the tree edit network
        delta_pred, types_pred, Cidx_pred, Cnum_pred = model(nodes, adj, X)
        # iterate over the tree and look for remaining addition operators
        delta = torch.zeros(len(nodes))
        types = torch.zeros(len(nodes), dtype=torch.long)
        # initializes types with the same type as before
        for i in range(len(nodes)):
            types[i] = alphabet.index(nodes[i])
        Cidx = torch.zeros(len(nodes), dtype = torch.long)
        Cnum = torch.zeros(len(nodes), dtype = torch.long)
        for i in range(len(nodes)):
            if nodes[i] == '+':
                # once we found an addition operator, check the right child
                right = adj[i][1]
                if nodes[right] == '0':
                    # if the right child is zero, we have reached our base case.
                    # So remove the + and the 0.
                    delta[i] = -1.
                    delta[right] = -1.
                elif nodes[right] == 'succ':
                    # if the right child is succ, insert a new 'succ' as parent
                    # of the left child and delete the current 'succ'
                    delta[i] = +1.
                    types[i] = alphabet.index('succ')
                    Cidx[i]  = 0
                    Cnum[i]  = 1
                    delta[right] = -1.
                elif nodes[right] != '+':
                    # if the right child is anything else, we need to re-write
                    # a number as the successor of another one, such that we
                    # can apply the previous rule in the next time step.
                    delta[i] = +1.
                    types[i] = alphabet.index('succ')
                    Cidx[i]  = 1
                    Cnum[i]  = 1
                    pred = str(int(nodes[right])-1)
                    types[right] = alphabet.index(pred)
            elif nodes[i] == 'succ' and (nodes[pi[i]] != '+' or pi[i] == i-1):
                # if we found a 'succ' operator which is not the right child of a
                # plus operator, we can try to resolve this succ operator
                child = adj[i][0]
                if nodes[child] not in ['succ', '+']:
                    delta[i] = -1.
                    succ     = str((int(nodes[child])+1) % 10)
                    types[child] = alphabet.index(succ)

        # compute the tree edit network loss, i.e. punish large scores if
        # we want deletions
        mask = delta < -0.5
        if torch.any(mask):
            loss = loss + torch.sum(torch.pow(torch.nn.functional.relu(delta_pred[mask] + 1.), 2))
            if verbose:
                print('deletion loss: %g' % loss.item())
                last_loss = loss.item()
        # punish scores that are large in absolute value if we want replacements
        mask = torch.abs(delta) < 0.5
        if torch.any(mask):
            loss = loss + torch.sum(torch.pow(torch.nn.functional.relu(torch.abs(delta_pred[mask]) - .25), 2))
            # and punish type errors for replacements as well
            loss = loss + torch.nn.functional.cross_entropy(types_pred[mask, :], types[mask], reduction='sum')
            if verbose:
                print('replacement loss: %g' % (loss.item() - last_loss))
                last_loss = loss.item()

        # punish scores that are small if we want insertions
        mask = delta > 0.5
        if torch.any(mask):
            loss = loss + torch.sum(torch.pow(torch.nn.functional.relu(-delta_pred[mask] + 1.), 2))
            # punish type misclassifications
            loss = loss + torch.nn.functional.cross_entropy(types_pred, types, reduction='sum')
            # punish child index misclassifications
            loss = loss + torch.nn.functional.cross_entropy(Cidx_pred[mask, :], Cidx[mask], reduction='sum')
            # punish wrong child association scores
            for i in torch.where(mask)[0]:
                if Cidx[i] >= len(adj[i]) or Cidx[i] + Cnum[i] > len(Cnum_pred[i, :]) or Cidx[i] + Cnum[i] > len(adj[i]):
                    raise ValueError('Internal error: child index was larger than expected')
                # punish small child scores for children that should be associated
                should_be_large = Cnum_pred[i, Cidx[i]:(Cidx[i] + Cnum[i])]
                loss = loss + torch.sum(torch.pow(torch.nn.functional.relu(-should_be_large + 1.), 2))
                # punish large child scores that should be small
                if Cidx[i] + Cnum[i] == len(adj[i]):
                    continue
                should_be_small = Cnum_pred[i, Cidx[i]+Cnum[i]]
                loss = loss + torch.pow(torch.nn.functional.relu(should_be_small), 2)


            if verbose:
                print('insertion loss: %g' % (loss.item() - last_loss))
                last_loss = loss.item()

    # return loss
    return loss

def predict_step(model, nodes, adj, alpha = None, verbose = False):
    """ A custom prediction function for tree edit networks to perform a
    single-step prediction on a given tree.

    Parameters
    ----------
    model: class pytorch_tree_edit_networks.TEN
        A tree edit network for which the prediction shall be computed.
    nodes: list
        the node list of the input tree.
    adj: list
        the adjacency list of the input tree.
    alpha: list (default = None)
        a custom alphabet. The Peano addition alphabet per default.
    verbose: bool (default = False)
        if set to True, prints diagnostic information.

    Returns
    -------
    script: class edist.tree_edits.Script
        An edit script which yields the output tree.
    nodes: list
        The node list of the output tree.
    adj: list
        The adjacency list of the output tree.

    """
    if alpha is None:
        alpha = alphabet

    if verbose:
        print('input tree: %s' % tree_utils.tree_to_string(nodes, adj, indent = True, with_indices = True))

    # construct the initial node features
    X = ten._degree_features(nodes, adj, model._dim_in_extra - 1, 0)
    # perform the prediction
    delta, types, Cidx, Cnum = model(nodes, adj, X)

    # initialize a new script
    script = tree_edits.Script()
    # perform replacements first
    for i in range(len(nodes)):
        if torch.abs(delta[i]) > 0.5:
            continue
        # retrieve the predicted type
        type_pred = int(torch.argmax(types[i, :]).item())
        type_pred = alpha[type_pred]
        # add a replacement if the type changes
        if type_pred != nodes[i]:
            script.append(tree_edits.Replacement(i, type_pred))

    # perform insertions and keep track of the indices
    ins_shift = np.zeros(len(nodes), dtype=int)
    for i in range(len(nodes)):
        if delta[i] <= 0.5:
            continue
        # retrieve the predicted type
        type_pred = torch.argmax(types[i, :]).item()
        type_pred = alpha[type_pred]
        # retrieve the predicted child index
        c = int(torch.argmax(Cidx[i, :]).item())
        # retrieve the predicted number of children
        C = 0
        while c + C < len(adj[i]) and Cnum[i, c + C] > 0.5:
            C += 1
        # set up the insertion
        script.append(tree_edits.Insertion(i + ins_shift[i], c, type_pred, C))
        # adjust the index shift
        if c < len(adj[i]):
            j = adj[i][c]
        else:
            j = i
            while adj[j]:
                j = adj[j][-1]
            j += 1
        ins_shift[j:] += 1

    # perform deletions in descending order to prevent additional index
    # interference and adjust the indices according to ins_shift
    for i in range(len(nodes)-1, -1, -1):
        if delta[i] >= -0.5:
            continue
        script.append(tree_edits.Deletion(i + ins_shift[i]))

    if verbose:
        print('predicted edits: %s' % str(script))

    # apply the script to obtain the result tree
    nodes, adj = script.apply(nodes, adj)
    # return result
    return script, nodes, adj


def peano_alignment(nodes, adj, next_nodes, next_adj):
    """ A custom alignment function between a tree and its successor according
    to _simplify. We need this function because the default alignments returned
    by edist.ted are needlessly hard to learn.

    Parameters
    ----------
    nodes: list
        The node list of the tree to be simplified.
    adj: list
        The adjacency list of the tree to be simplified.
    next_nodes: list
        The node list of the simplified tree.
    next_adj: list
        The adjacency list of the simplified tree.

    Returns
    -------
    alignment: class edist.alignment.Alignment
        The alignment between nodes and next_nodes.

    """
    # retrieve the parent of each node
    pi = np.zeros(len(nodes), dtype=int)
    for i in range(len(nodes)):
        for j in adj[i]:
            pi[j] = i
    # maintain an array to keep track of the index shift
    index_shift = np.zeros(len(nodes), dtype=int)
    # build a mapping from the current tree to the next tree
    left_to_right = {}
    # iterate over the tree and look for remaining addition operators
    for i in range(len(nodes)):
        if nodes[i] == '+':
            # once we found an addition operator, check the right child
            right = adj[i][1]
            if nodes[right] == '0':
                # if the right child is zero, we have reached our base case.
                # remove the + operator and the zero.
                left_to_right[i] = -1
                index_shift[i:] -= 1
                left_to_right[right] = -1
                index_shift[right+1:] -= 1
            elif nodes[right] == 'succ':
                # if the right child is succ, insert a new 'succ' as parent
                # of the left child and delete the current 'succ'
                index_shift[i+1:right+1] += 1
                left_to_right[right] = -1
            elif nodes[right] != '+':
                # if the right child is anything else, we need to re-write
                # a number as the successor of another one, such that we
                # can apply the previous rule in the next time step.
                index_shift[right:] += 1
        elif nodes[i] == 'succ' and (nodes[pi[i]] != '+' or pi[i] == i-1):
            # if we found a 'succ' operator and the parent is _not_ a
            # plus operator, we can try to resolve this succ operator
            child = adj[i][0]
            if nodes[child] not in ['succ', '+']:
                left_to_right[i] = -1
                index_shift[i:] -= 1
        if i not in left_to_right:
            left_to_right[i] = i + index_shift[i]
    # build the alignment
    alignment = Alignment()
    i, j = 0, 0
    while i < len(nodes):
        if left_to_right[i] < 0:
            alignment.append_tuple(i, -1)
        else:
            while j < left_to_right[i]:
                alignment.append_tuple(-1, j)
                j += 1
            alignment.append_tuple(i, j)
            j += 1
        i += 1
    # return
    return alignment
