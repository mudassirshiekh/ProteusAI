import random
import numpy as np
import sys
sys.path.append('../sampler')
from sampler import constraints


class SequenceOptimizer:
    """
    Optimizes a protein sequence based on a custom energy function. Set weights of constraints to 0 which you don't want to use.

    Parameters:
        native_seq (str): native sequence to be optimized
        sampler (str): choose between simulated_annealing and substitution sampler. Default simulated annealing
        n_traj (int): number of trajectories.
        n_iter (int): number of sampling intervals per trajectory. For simulated annealing, the number of iterations is often chosen in the range of [1,000, 10,000].
        mut_p (tuple): probabilities for substitution, insertion and deletion. Default [0.6, 0.2, 0.2]
        T (float): sampling temperature. For simulated annealing, T0 is often chosen in the range [1, 100]. default 10
        M (float): rate of temperature decay. or simulated annealing, a is often chosen in the range [0.01, 0.1] or [0.001, 0.01]. Default 0.01
        length_constraint (tuple): constraint on length. (maximum_allowed_length(int), weight_of_constraint(float))
        w_max_len (float): weight of the length constraint
    """

    def __init__(self, native_seq: str = None, sampler: str = 'simulated_annealing',
                 n_traj: int = 5, n_iter: int = 1000, mut_p: tuple = (0.6, 0.2, 0.2),
                 T: float = 10., M: float = 0.01,
                 length_constraint: tuple = (200, 0)
                 ):

        self.native_seq = native_seq
        self.sampler = sampler
        self.n_traj = n_traj
        self.n_iter = n_iter
        self.mut_p = mut_p
        self.T = T
        self.M = M
        self.length_constraint = length_constraint
        self.max_len = int(length_constraint[0])
        self.w_max_len = float(length_constraint[1])

    def __str__(self):
        l = ['ProteusAI.MCMC.SequenceOptimizer class: \n',
             '---------------------------------------\n',
             'When SequenceOptimizer.run() is called sequence optimization will be performed on sequence:\n\n',
             f'{self.native_seq}\n',
             '\nThe following variables were set:\n\n',
             'variable\t|value\n',
             '----------------+-------------------\n',
             f'sampler: \t|{self.sampler}\n',
             f'n_traj: \t|{self.n_traj}\n',
             f'n_iter: \t|{self.n_iter}\n',
             f'mut_p: \t\t|{self.mut_p}\n',
             f'T: \t\t|{self.T}\n',
             f'M: \t\t|{self.M}\n\n',
             f'The energy function is a linear combination of the following constraints:\n\n',
             f'constraint\t|value\t|weight\n',
             '----------------+-------+------------\n',
             f'length \t\t|{self.max_len}\t|{self.w_max_len}\n',
             ]
        s = ''.join(l)
        return s

    ### SAMPLERS
    def mutate(self, seqs, mut_p: list = (0.6, 0.2, 0.2)):
        """
        mutates input sequences.

        Parameters:
            seqs (list): list of peptide sequences

        Returns:
            list: mutated sequences
        """
        AAs = ('A', 'C', 'D', 'E', 'F', 'G', 'H',
               'I', 'K', 'L', 'M', 'N', 'P', 'Q',
               'R', 'S', 'T', 'V', 'W', 'Y')

        mut_types = ('substitution', 'insertion', 'deletion')

        mutated_seqs = []
        for seq in seqs:
            mut_type = random.choices(mut_types, mut_p)[0]
            if mut_type == 'substitution':
                pos = random.randint(0, len(seq) - 1)
                replacement = random.choice(AAs)
                mut_seq = ''.join([seq[:pos], replacement, seq[pos + 1:]])
                mutated_seqs.append(mut_seq)

            elif mut_type == 'insertion':
                pos = random.randint(0, len(seq) - 1)
                insertion = random.choice(AAs)
                mut_seq = ''.join([seq[:pos], insertion, seq[pos:]])
                mutated_seqs.append(mut_seq)

            elif mut_type == 'deletion' and len(seq) > 1:
                pos = random.randint(0, len(seq) - 1)
                l = list(seq)
                del l[pos]
                mut_seq = ''.join(l)
                mutated_seqs.append(mut_seq)

            else:
                pos = random.randint(0, len(seq) - 1)
                insertion = random.choice(AAs)
                mut_seq = ''.join([seq[:pos], insertion, seq[pos:]])
                mutated_seqs.append(mut_seq)

        return mutated_seqs

    ### ENERGY FUNCTION and ACCEPTANCE CRITERION
    def energy_function(self, seqs: list, i):
        """
        Combines constraints into an energy function.

        Parameters:
            seqs (list): list of sequences

        Returns:
            list: Energy value
        """
        energies = np.zeros(len(seqs))

        energies += self.w_max_len * constraints.length_constraint(seqs=seqs, max_len=self.max_len)

        names = [f'structure_{j}_cycle{i}' for j in range(len(seqs))]
        headers, pdbs, pTMs, pLDDTs = constraints.structure_prediction(seqs, names)
        with open('test_output', 'w') as f:
            for i in range(len(seqs)):
                lines = [headers[i], seqs[i], pLDDTs[i], pTMs[i]]
                for line in lines:
                    f.writelines(line+'\n')

        for i, pdb in enumerate(pdbs):
            with open(f'test_pdb_{i}.pdb', 'w') as f:
                f.writelines(pdb)

        return energies

    def p_accept(self, E_x_mut, E_x_i, T, i, M):
        """
        Decides to accep or reject changes.
        """

        T = T / (1 + M * i)
        dE = E_x_i - E_x_mut
        exp_val = np.exp(1 / (T * dE))
        p_accept = np.minimum(exp_val, np.ones_like(exp_val))
        return p_accept

    ### RUN
    def run(self):
        """
        Runs MCMC-sampling based on user defined inputs. Returns optimized sequences.
        """
        native_seq = self.native_seq
        n_traj = self.n_traj
        n_iter = self.n_iter
        sampler = self.sampler
        energy_function = self.energy_function
        T = self.T
        M = self.M
        p_accept = self.p_accept
        mut_p = self.mut_p

        if sampler == 'simulated_annealing':
            mutate = self.mutate

        if native_seq is None:
            raise 'The optimizer needs a sequence to run. Define a sequence by calling SequenceOptimizer(native_seq = <your_sequence>)'

        seqs = [native_seq for _ in range(n_traj)]

        for i in range(n_iter):
            mut_seqs = mutate(seqs, mut_p)
            E_x_i = energy_function(seqs, i)
            E_x_mut = energy_function(mut_seqs, i)

            # accept or reject change
            p = p_accept(E_x_mut, E_x_i, T, i, M)

            for n in range(len(p)):
                if p[n] > random.random():
                    seqs[n] = mut_seqs[n]

        return (seqs)