# This source code is part of the proteusAI package and is distributed
# under the MIT License.

__name__ = "proteusAI"
__author__ = "Jonathan Funk"

import os
import sys
current_path = os.path.dirname(os.path.abspath(__file__))
root_path = os.path.join(current_path, '..')
sys.path.append(root_path)
import torch
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.svm import SVC, SVR
from sklearn.model_selection import KFold
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
import proteusAI.io_tools as io_tools
import proteusAI.visual_tools as vis
from proteusAI.ml_tools.torch_tools import GP, predict_gp, computeR2
import proteusAI.ml_tools.bo_tools as BO
import random
from typing import Union
import json
from joblib import dump
import csv
import torch
import pandas as pd
import gpytorch
import numpy as np


class Model:
    """
    The Model object allows the user to create machine learning models, using 
    Library objects as input. 

    Attributes:
        model: Class variable holding the model.
        library (proteusAI.Library): Library object to train a model. Default None.
        model (str): Type of model to create. Default random forrest ('rf').
        x (str): Choose vector representation for 'x'. Default 'ohe'.
        split (str): Choose data split. Default random split.
        k_folds (int): Choose k for k-fold cross validation. Default None.
        grid_search (bool): Performe a grid search. Default 'False'.
        custom_params (dict): Provide a dictionary or json file with custom parameters. Default None.
        custom_model (torch.nn.Module): Provide a custom PyTorch model.
        optim (str): Optimizer for training PyTorch models. Default 'adam'.
        lr (float): Learning rate for training PyTorch models. Default 10e-4.
        seed (int): random seed. Default 21.
        test_true (list): List of true values of the test dataset.
        test_predictions (list): Predicted values of the test dataset.
        test_r2 (float): R-squared value of the model on the test set.
        val_true (list): List of true values of the validation dataset.
        val_predictions (list): Predicted values of the validation dataset.
        val_r2 (float): R-squared value of the model on the validation dataset.
    """

    _sklearn_models = ['rf', 'knn', 'svm', 'ffnn']
    _pt_models = ['gp']
    _in_memory_representations = ['ohe', 'blosum50', 'blosum62']
    
    def __init__(self, **kwargs):
        """
        Initialize a new model.

        Args:
            model: Contains the trained model.
            library (proteusAI.Library): Library object to train a model. Default None.
            model_type (str): Type of model to create. Default random forrest ('rf').
            x (str): Choose vector representation for 'x'. Default 'ohe'.
            split (str): Choose data split. Default random split.
            k_folds (int): Choose k for k-fold cross validation. Default None.
            grid_search (bool): Performe a grid search. Default 'False'.
            custom_params (dict): Provide a dictionary or json file with custom parameters. Default None.
            custom_model (torch.nn.Module): Provide a custom PyTorch model.
            optim (str): Optimizer for training PyTorch models. Default 'adam'.
            lr (float): Learning rate for training PyTorch models. Default 10e-4.
            seed (int): random seed. Default 21.
        """
        self._model = None
        self.train_data = []
        self.test_data = []
        self.val_data = []
        self.test_true = []
        self.test_predictions = []
        self.val_true = []
        self.val_predictions = []
        self.test_r2 = []
        self.val_r2 = []
        self.rep_path = None
        self.dest = None
        self.y_best = None

        # check for device
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # Set attributes using the provided kwargs
        self._set_attributes(**kwargs)

    
    ### args
    def _set_attributes(self, **kwargs):
        defaults = {
            'library': None,
            'model_type': 'rf',
            'x': 'ohe',
            'rep_path': None,
            'split': (80,10,10),
            'k_folds': None,
            'grid_search': False,
            'custom_params': None,
            'custom_model': None,
            'optim': 'adam',
            'lr': 10e-4,
            'seed': 42,
            'dest' : None
        }
        
        # Update defaults with provided keyword arguments
        defaults.update(kwargs)

        for key, value in defaults.items():
            setattr(self, key, value)

    def _update_attributes(self, **kwargs):
        defaults = {
            'library': None,
            'model_type': 'rf',
            'x': 'ohe',
            'rep_path': None,
            'split': (80,10,10),
            'k_folds': None,
            'grid_search': False,
            'custom_params': None,
            'custom_model': None,
            'optim': 'adam',
            'lr': 10e-4,
            'seed': 42,
            'dest' : None
        }
        
        # Update defaults with provided keyword arguments
        defaults.update(kwargs)
        
        for key, value in kwargs.items():
            setattr(self, key, value)

    def train(self, **kwargs):
        """
        Train the model.

        Args:
            library (proteusAI.Library): Data for training.
            model_type (str): choose the model type ['rf', 'svm', 'knn', 'ffnn'],
            x (str): choose the representation type ['esm2', 'esm1v', 'ohe', 'blosum50', 'blosum62'].
            rep_path (str): Path to representations. Default None - will extract from library object.
            split (tuple or dict): Choose the split ratio of training, testing and validation data as a tuple. Default (80,10,10).
                                   Alternatively, provide a dictionary of proteins, with the keys 'train', 'test', and 'val', with
                                   list of proteins as values for custom data splitting. 
            k_folds (int): Number of folds for cross validation.
            grid_search: Enable grid search.
            custom_params: None. Not implemented yet.
            custom_model: None. Not implemented yet.
            optim (str): Choose optimizer for feed forward neural network. e.g. 'adam'.
            lr (float): Choose a learning rate for feed forward neural networks. e.g. 10e-4.
            seed (int): Choose a random seed. e.g. 42
        """
        # Update attributes if new values are provided
        self._update_attributes(**kwargs)

        # split data
        self.train_data, self.test_data, self.val_data = self.split_data()

        # load model
        self._model = self.model()

        # train
        if self.model_type in self._sklearn_models:
            self.train_sklearn(rep_path=self.rep_path)
        elif self.model_type in self._pt_models:
            self.train_gp(rep_path=self.rep_path)
        else:
            raise ValueError(f"The training method for '{self.model_type}' models has not been implemented yet")

  
    ### Helpers ###
    def split_data(self):
        """
        Split data into train, test, and validation sets.

            1. 'random': Randomly splits data points
            2. 'site': Splits data by sites in the protein,
                such that the same site cannot be found
                in the training, testing and validation set
            3. 'custom': Splits the data according to a custom pattern

        Returns:
            tuple: returns three lists of train, test and validation proteins.
        """

        proteins = self.library.proteins

        random.seed(self.seed)

        train_data, test_data, val_data = [], [], []

        if type(self.split) == tuple:
            train_ratio, test_ratio, val_ratio = tuple(value / sum(self.split) for value in self.split)
            train_size = int(train_ratio * len(proteins))
            test_size = int(test_ratio * len(proteins))

            random.shuffle(proteins)

            # Split the data
            train_data = proteins[:train_size]
            test_data = proteins[train_size:train_size + test_size]
            val_data = proteins[train_size + test_size:]

        # custom datasplit
        elif type(self.split) == dict:
            train_data = self.split['train']
            test_data = self.split['test']
            val_data = self.split['val']
            
        # TODO: implement other splitting methods
        else:
            raise ValueError(f"The {self.split} split has not been implemented yet...")
        
        return train_data, test_data, val_data
    

    def load_representations(self, proteins: list, rep_path: Union[str, None] = None):
        """
        Loads representations for a list of proteins.

        Args:
            proteins (list): List of proteins.
            rep_path (str): Path to representations. If None, the method assumes the
                library project path and the representation type used for training.

        Returns:
            list: List of representations.
        """
        torch.manual_seed(self.seed)
        torch.cuda.manual_seed_all(self.seed)

        reps = self.library.load_representations(rep=self.x, proteins=proteins)

        return reps


    def model(self, **kwargs):
        """
        Load or create model according to user specifications and parameters.

        For a complete list and detailed explanation of model parameters, refer to the scikit-learn documentation.
        """

        model_type = self.model_type
        model = None

        # Define the path for the params.json and model
        if self.dest != None:
            params_path = f"{self.dest}/params.json"
        else:
            params_path = os.path.join(f"{self.library.rep_path}", f"../models/{self.model_type}/{self.x}/params.json")

        # Check if params.json exists
        if not os.path.exists(params_path):
            os.makedirs(os.path.dirname(params_path), exist_ok=True)
            with open(params_path, 'w') as f:
                json.dump(kwargs, f)

        if model_type in self._sklearn_models:
            model_params = kwargs.copy()
            #model_params['seed'] = self.seed

            if self.y_type == 'class':
                if model_type == 'rf':
                    model = RandomForestClassifier(**model_params)
                elif model_type == 'svm':
                    model = SVC(**model_params)
                elif model_type == 'knn':
                    model = KNeighborsClassifier(**model_params)
            elif self.y_type == 'num':
                if model_type == 'rf':
                    model = RandomForestRegressor(random_state=self.seed, **model_params)
                elif model_type == 'svm':
                    model = SVR(**model_params)
                elif model_type == 'knn':
                    model = KNeighborsRegressor(**model_params)
                
            return model
        
        elif model_type in self._pt_models:
            if self.y_type == 'class':
                if model_type == 'gp':
                    raise ValueError(f"Model type '{model_type}' has not been implemented yet")
            elif self.y_type == 'num':
                if model_type == 'gp':
                    model = 'GP_MODEL'

            return model
        
        else:
            raise ValueError(f"Model type '{model_type}' has not been implemented yet")

    

    def train_sklearn(self, rep_path):
        """
        Train sklearn models and save the model.

        Args:
            rep_path (str): representation path
        """
        assert self._model is not None

        # This is for representations that are not stored in memory
        train = self.load_representations(self.train_data, rep_path=rep_path)
        test = self.load_representations(self.test_data, rep_path=rep_path)
        val = self.load_representations(self.val_data, rep_path=rep_path)

        # handle representations that are not esm
        if len(train[0].shape) == 2:
            train = [x.view(-1) for x in train]
            test = [x.view(-1) for x in test]
            val = [x.view(-1) for x in val]

        x_train = torch.stack(train).cpu().numpy()
        x_test = torch.stack(test).cpu().numpy()
        x_val = torch.stack(val).cpu().numpy()

        # TODO: For representations that are stored in memory the computation happens here:

        y_train = [protein.y for protein in self.train_data]
        self.y_test = [protein.y for protein in self.test_data]
        self.y_val = [protein.y for protein in self.val_data]
        self.val_names = [protein.name for protein in self.val_data]

        if self.k_folds is None:
            # train model
            self._model.fit(x_train, y_train)

            # prediction on test set
            self.test_r2 = self._model.score(x_test, self.y_test)
            self.y_test_pred = self._model.predict(x_test)

            # prediction on validation set
            self.val_r2 = self._model.score(x_val, self.y_val)
            self.y_val_pred = self._model.predict(x_val)
            self.y_val_sigma = [None]*len(self.y_val)
            self.y_test_sigma = [None]*len(self.y_test)

            # Save the model
            if self.dest != None:
                model_save_path = f"{self.dest}/model.joblib"
                csv_dest = f"{self.dest}"
            else:
                model_save_path = os.path.join(f"{self.library.rep_path}", f"../models/{self.model_type}/{self.x}/model.joblib")
                csv_dest = os.path.join(f"{self.library.rep_path}",f"../models/{self.model_type}/{self.x}")

            os.makedirs(os.path.dirname(model_save_path), exist_ok=True)
            dump(self._model, model_save_path)

            self.save_to_csv(self.train_data, y_train, [None]*len(y_train), [None]*len(y_train),f"{csv_dest}/train_data.csv")
            self.save_to_csv(self.test_data, self.y_test, self.y_test_pred, self.y_test_sigma,f"{csv_dest}/test_data.csv")
            self.save_to_csv(self.val_data, self.y_val, self.y_val_pred, self.y_val_sigma,f"{csv_dest}/val_data.csv")

            # Save results to a JSON file
            results = {
                'test_r2': self.test_r2,
                'val_r2': self.val_r2
            }
            with open(f"{csv_dest}/results.json", 'w') as f:
                json.dump(results, f)

        # handle ensembles
        else:
            kf = KFold(n_splits=self.k_folds, shuffle=True, random_state=self.seed)
            x_train = np.concatenate([x_train, x_test])
            y_train = y_train + self.y_test
            fold_results = []
            ensemble = []

            for train_index, test_index in kf.split(x_train):
                x_train_fold, x_test_fold = x_train[train_index], x_train[test_index]
                y_train_fold, y_test_fold = np.array(y_train)[train_index], np.array(y_train)[test_index]

                self._model.fit(x_train_fold, y_train_fold)
                test_r2 = self._model.score(x_test_fold, y_test_fold)
                fold_results.append(test_r2)
                ensemble.append(self._model)

            avg_test_r2 = np.mean(fold_results)

            # Store model ensemble as model
            self._model = ensemble

            # Prediction on validation set
            self.val_data, self.y_val_pred, self.y_val_sigma, self.y_val, _ = self.predict(self.val_data)
            self.val_r2 = self.score(self.val_data)

            # Save the model
            if self.dest is not None:
                csv_dest = f"{self.dest}"
            else:
                csv_dest = os.path.join(f"{self.library.rep_path}", f"../models/{self.model_type}/{self.x}")

            for i, model in enumerate(ensemble):
                if self.dest is not None:
                    model_save_path = f"{self.dest}/model_{i}.joblib"
                else:
                    model_save_path = os.path.join(f"{self.library.rep_path}", f"../models/{self.model_type}/{self.x}/model_{i}.joblib")

                os.makedirs(os.path.dirname(model_save_path), exist_ok=True)
                dump(model, model_save_path)

            # Save the sequences, y-values, and predicted y-values to CSV
            self.save_to_csv(self.train_data, y_train, [None] * len(y_train), [None] * len(y_train), f"{csv_dest}/train_data.csv")
            self.save_to_csv(self.val_data, self.y_val, self.y_val_pred, self.y_val_sigma,f"{csv_dest}/val_data.csv")

            # Save results to a JSON file
            results = {
                'k_fold_test_r2': fold_results,
                'avg_test_r2': avg_test_r2,
                'val_r2': self.val_r2
            }
            with open(f"{csv_dest}/results.json", 'w') as f:
                json.dump(results, f)
    

    # Save the sequences, y-values, and predicted y-values to CSV
    def save_to_csv(self, proteins, y_values, y_pred_values, y_sigma_values ,filename):
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['sequence', 'y-value', 'y-predicted'])  # CSV header
            for protein, y, y_pred in zip(proteins, y_values, y_pred_values):
                writer.writerow([protein.seq, y, y_pred])


    def train_gp(self, rep_path, epochs=150, initial_lr=0.1, final_lr=1e-6, decay_rate=0.1):
        """
        Train a Gaussian Process model and save the model.

        Args:
            rep_path (str): representation path
        """
        assert self._model is not None

        # This is for representations that are not stored in memory
        train = self.load_representations(self.train_data, rep_path=rep_path)
        test = self.load_representations(self.test_data, rep_path=rep_path)
        val = self.load_representations(self.val_data, rep_path=rep_path)

        # handle representations that are not esm
        if len(train[0].shape) == 2:
            train = [x.view(-1) for x in train]
            test = [x.view(-1) for x in test]
            val = [x.view(-1) for x in val]

        x_train = torch.stack(train).to(device=self.device)
        x_test = torch.stack(test).to(device=self.device)
        x_val = torch.stack(val).to(device=self.device)

        y_train = torch.stack([torch.Tensor([protein.y]) for protein in self.train_data]).view(-1).to(device=self.device)
        self.y_test = torch.stack([torch.Tensor([protein.y]) for protein in self.test_data]).view(-1).to(device=self.device)
        y_val = torch.stack([torch.Tensor([protein.y])  for protein in self.val_data]).view(-1).to(device=self.device)
        self.val_names = [protein.name for protein in self.val_data]

        self.likelihood = gpytorch.likelihoods.GaussianLikelihood().to(device=self.device)
        self._model = GP(x_train, y_train, self.likelihood).to(device=self.device)
        fix_mean = True
        
        optimizer = torch.optim.Adam(self._model.parameters(), lr=initial_lr)
        scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer, gamma=decay_rate)
        mll = gpytorch.mlls.ExactMarginalLogLikelihood(self.likelihood, self._model)

        for param in self._model.named_parameters(): 
            print(param)

        # model.mean_module.constant.data.fill_(1)  # FIX mean to 1
        self._model.train()
        self.likelihood.train()
        prev_loss = float('inf')
        #TODO: abstract this away
        for _ in range(epochs):
            optimizer.zero_grad()
            output = self._model(x_train)
            loss = -mll(output, y_train)
            loss.backward()
            optimizer.step()
            scheduler.step()

            # Check for convergence
            if abs(prev_loss - loss.item()) < 0.0001:
                print(f'Convergence reached. Stopping training...')
                break
            
            prev_loss = loss.item()

        print(f'Training completed. Final loss: {loss.item()}')   
        
        # prediction on test set
        y_test_pred, y_test_sigma = predict_gp(self._model, self.likelihood, x_test)
        self.test_r2 = computeR2(self.y_test, y_test_pred)
        self.y_test_pred, self.y_test_sigma  = y_test_pred.cpu().numpy(), y_test_sigma.cpu().numpy()

        # prediction on validation set
        y_val_pred, y_val_sigma = predict_gp(self._model, self.likelihood, x_val)
        self.val_r2 = computeR2(y_val, y_val_pred)
        self.y_train = y_train.cpu().numpy()
        self.y_test_pred, self.y_test_sigma = y_test_pred.cpu().numpy(), y_test_sigma.cpu().numpy()
        self.y_val_pred, self.y_val_sigma = y_val_pred.cpu().numpy(), y_val_sigma.cpu().numpy()

        self.y_val = y_val.cpu().numpy()
        self.y_test = self.y_test.cpu().numpy()

        self.y_best = max((max(self.y_train), max(self.y_test), max(self.y_val)))

        # Save the model
        if self.dest != None:
            model_save_path = f"{self.dest}/model.pt"
            csv_dest = self.dest
        else:
            model_save_path = os.path.join(f"{self.library.rep_path}",f"../models/{self.model_type}/{self.x}/model.pt")
            csv_dest = os.path.join(f"{self.library.rep_path}", f"../models/{self.model_type}/{self.x}")

        # Save the model
        os.makedirs(os.path.dirname(model_save_path), exist_ok=True)
        torch.save(self._model.state_dict(), model_save_path)

        # Save the sequences, y-values, and predicted y-values to CSV
        def save_to_csv(proteins, y_values, y_pred_values, y_pred_sigma, filename):
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['sequence', 'y-value', 'y-predicted', 'sigma'])  # CSV header
                for protein, y, y_pred, y_sig in zip(proteins, y_values, y_pred_values, y_pred_sigma):
                    writer.writerow([protein.seq, y, y_pred, y_sig])

        save_to_csv(self.train_data, y_train, [None]*len(y_train), [None]*len(y_train),f"{csv_dest}/train_data.csv")
        save_to_csv(self.test_data, self.y_test, self.y_test_pred, self.y_test_sigma, f"{csv_dest}/test_data.csv")
        save_to_csv(self.val_data, self.y_val, self.y_val_pred,  self.y_val_sigma, f"{csv_dest}/val_data.csv")

        # Save results to a JSON file
        results = {
            'test_r2': self.test_r2,
            'val_r2': self.val_r2,
        }

        with open(f"{csv_dest}/results.json", 'w') as f:
            json.dump(results, f)
    

    def predict(self, proteins: list, rep_path=None, acq_fn='greedy', batch_size=1000):
        """
        Scores the R-squared value for a list of proteins.

        Args:
            proteins (list): List of proteins to make predictions.
            rep_path (str): Path to representations for proteins in the list.
                If None, the library project path and representation type for training
                will be assumed

        Returns:
            list: Predictions generated by the model.
        """
        if self._model is None:
            raise ValueError("Model is 'None'")

        if acq_fn == 'ei':
            acq = BO.EI
        elif acq_fn == 'greedy':
            acq = BO.greedy
        elif acq_fn == 'ucb':
            acq = BO.UCB
        elif acq_fn == 'random':
            acq = BO.random_acquisition

        all_y_pred = []
        all_sigma_pred = []
        all_acq_scores = []

        for i in range(0, len(proteins), batch_size):
            batch_proteins = proteins[i:i + batch_size]
            batch_reps = self.load_representations(batch_proteins, rep_path)

            if len(batch_reps[0].shape) == 2:
                batch_reps = [x.view(-1) for x in batch_reps]

            # GP
            if self.model_type == 'gp':
                self.likelihood.eval()
                x = torch.stack(batch_reps).to(device=self.device)
                y_pred, sigma_pred = predict_gp(self._model, self.likelihood, x)
                y_pred = y_pred.cpu().numpy()
                sigma_pred = sigma_pred.cpu().numpy()
                acq_score = acq(y_pred, sigma_pred, self.y_best)

            # Handle ensembles
            elif isinstance(self._model, list):
                ys = []
                for model in self._model:
                    x = torch.stack(batch_reps).cpu().numpy()
                    y_pred = model.predict(x)
                    ys.append(y_pred)
        
                y_stack = np.stack(ys)
                y_pred = np.mean(y_stack, axis=0)
                sigma_pred = np.std(y_stack, axis=0)
                acq_score = acq(y_pred, sigma_pred, self.y_best)
            
            # Handle single model
            else:
                x = torch.stack(batch_reps).cpu().numpy()
                y_pred = self._model.predict(x)
                sigma_pred = np.zeros_like(y_pred)
                acq_score = acq(y_pred, sigma_pred, self.y_best)

            all_y_pred.extend(y_pred)
            all_sigma_pred.extend(sigma_pred)
            all_acq_scores.extend(acq_score)

        all_y_pred = np.array(all_y_pred)
        all_sigma_pred = np.array(all_sigma_pred)
        all_acq_scores = np.array(all_acq_scores)

        # Sort acquisition scores and get sorted indices
        sorted_indices = np.argsort(all_acq_scores)[::-1]

        # Sort all lists/arrays by the sorted indices
        val_data = [proteins[i] for i in sorted_indices]
        y_val = [prot.y for prot in val_data]
        y_val_pred = all_y_pred[sorted_indices]
        y_val_sigma = all_sigma_pred[sorted_indices]
        sorted_acq_score = all_acq_scores[sorted_indices]

        return val_data, y_val_pred, y_val_sigma, y_val, sorted_acq_score
    

    def score(self, proteins: list, rep_path = None):
        """
        Make predictions for a list of proteins.

        Args:
            proteins (list): List of proteins to make predictions.
            rep_path (str): Path to representations for proteins in the list.
                If None, the library project path and representation type for training
                will be assumed

        Returns:
            list: Predictions generated by the model.
        """

        if self._model is None:
            raise ValueError(f"Model is 'None'")
        
        reps = self.load_representations(proteins, rep_path)

        if len(reps[0].shape) == 2:
            reps = [x.view(-1) for x in reps]

        x = torch.stack(reps).cpu().numpy()
        y = [protein.y for protein in proteins]

        # ensemble
        ensemble_scores = []
        if type(self._model) == list:
            for model in self._model:
                score = model.score(x,y)
                ensemble_scores.append(score)
            ensemble_scores = np.stack(ensemble_scores)
            scores = np.mean(ensemble_scores, axis=0)
        else:
            scores = self._model.score(x, y)
        

        return scores
    

    def true_vs_predicted(self, y_true: list, y_pred: list, title: Union[str, None] = None, 
                          x_label: Union[str, None] = None, y_label: Union[str, None] = None , plot_grid: bool = True, 
                          file: Union[str, None] = None, show_plot: bool = False):
        """
        Predicts true values versus predicted values.

        Args:
            y_true (list): True y values.
            y_pred (list): Predicted y values.
            title (str): Set the title of the plot. 
            x_label (str): Set the x-axis label.
            y_label (str): Set the y-axis label.
            plot_grid (bool): Display a grid in the plot.
            file (str): Choose a file name.
            show_plot (bool): Choose to show the plot.
        """
        
        if self.dest:
            dest = os.path.join(self.dest, f"plots")
        else:
            dest = os.path.join(self.library.rep_path, f'../models/{self.model_type}/{self.x}/plots')
        if not os.path.exists(dest):
            os.makedirs(dest)

        fig, ax = vis.plot_predictions_vs_groundtruth(y_true, y_pred, title, x_label, 
                                            y_label, plot_grid, file, show_plot)
        
        return fig, ax
    
    ### Getters and Setters ###
    # Getter and Setter for library
    @property
    def library(self):
        return self._library
    
    @library.setter
    def library(self, library):
        self._library = library
        if library is not None:
            self.y_type = library.y_type

    # Getter and Setter for model_type
    @property
    def model_type(self):
        return self._model_type
    
    @model_type.setter
    def model_type(self, model_type):
        self._model_type = model_type

    # Getter and Setter for x
    @property
    def x(self):
        return self._x
    
    @x.setter
    def x(self, x):
        self._x = x

    # Getter and Setter for split
    @property
    def split(self):
        return self._split
    
    @split.setter
    def split(self, split):
        self._split = split

    # Getter and Setter for k_folds
    @property
    def k_folds(self):
        return self._k_folds
    
    @k_folds.setter
    def k_folds(self, k_folds):
        self._k_folds = k_folds

    # Getter and Setter for grid_search
    @property
    def grid_search(self):
        return self._grid_search
    
    @grid_search.setter
    def grid_search(self, grid_search):
        self._grid_search = grid_search

    # Getter and Setter for custom_params
    @property
    def custom_params(self):
        return self._custom_params
    
    @custom_params.setter
    def custom_params(self, custom_params):
        self._custom_params = custom_params

    # Getter and Setter for custom_model
    @property
    def custom_model(self):
        return self._custom_model
    
    @custom_model.setter
    def custom_model(self, custom_model):
        self._custom_model = custom_model

    # Getter and Setter for optim
    @property
    def optim(self):
        return self._optim
    
    @optim.setter
    def optim(self, optim):
        self._optim = optim

    # Getter and Setter for lr
    @property
    def lr(self):
        return self._lr
    
    @lr.setter
    def lr(self, lr):
        self._lr = lr

    # Getter and Setter for seed
    @property
    def seed(self):
        return self._seed
    
    @seed.setter
    def seed(self, seed):
        self._seed = seed