import os
import joblib
import numpy as np
import pandas as pd
import scipy.stats as st

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import (
    KFold,
    RandomizedSearchCV,
    train_test_split,
)

SEED = 17
TRAINING_DATA_DIR = os.path.join("..", "training-data")
SAVE_DIR = os.path.join("..", "grid-search-results")


def load_csv(filename, data_dir=TRAINING_DATA_DIR):
    """
    Args:
        filename (string): The name of the file to load. (.csv)
        data_dir (string, optional): The name of the directory to load from. Defaults to TRAINING_DATA_DIR.

    Returns:
        pandas.DataFrame
    """
    return pd.read_csv(os.path.join(data_dir, filename))


def map_target_values(df, target, new_target_name, encoding):
    """
    Args:
        df (pandas.DataFrame): The dataframe to map the target values.
        target (string): The name of the target column.
        new_target_name (string): The name of the new target column.
        encoding (lambda function): A lambda function to map the target values.
            e.g. lambda x: np.log(np.abs(x))

    Returns:
        pandas.DataFrame
    """
    df[new_target_name] = df[target].map(encoding)
    return df


def split_train_test(
    df,
    target,
    features,
    test_size=0.10,
    random_state=SEED,
    check_shape=True,
):
    """
    Args:
        df (pandas.DataFrame): The dataframe to split.
        target (string): The name of the target column.
        features (list, optional): The list of feature column names to use.
        test_size (float, optional): The proportion of the data to include in the test split. Defaults to 0.10.
        random_state (int, optional): Controls the shuffling applied to the data before applying the split. Defaults to the global seed.
        check_shape (bool, optional): If True, will check the shape of the training and testing data. Defaults to True.

    Returns:
        (lists) : X_train, X_test, y_train, y_test
    """
    assert len(features) > 0, "No feature columns provided"

    Y = df[target].values.reshape(-1, 1)
    X = df[features]

    X_train, X_test, Y_train, Y_test = train_test_split(
        X, Y, test_size=test_size, random_state=random_state
    )

    if check_shape:
        print(f"X_train shape: {X_train.shape}")
        print(f"X_test shape: {X_test.shape}")
        print(f"y_train shape: {Y_train.shape}")
        print(f"y_test shape: {Y_test.shape}")

        if X_train.shape[0] != Y_train.shape[0]:
            raise ValueError("X_train and Y_train have different number of samples")

    return X_train, X_test, Y_train, Y_test


def search_random_params(
    X_train,
    Y_train,
    model,
    param_dists,
    cv=5,
    n_iters=100,
    n_jobs=1,
    verbose=2,
    scoring="neg_mean_absolute_error",
    random_state=SEED,
    keep_train_score=False,
    filename="rf_reg.pkl",
    save_dir=SAVE_DIR,
    save_best=True,
    best_name="rf_reg_best-estm.pkl",
    remake=False,
):
    """
    Args:
        X_train (array-like): The training input samples.
        Y_train (array-like): The target values.
        model (sklearn.base.BaseEstimator): The model to fit.
        param_dists (dict): Dictionary with parameters names (string) as keys and distributions or lists of parameters to try.
        cv (int, cross-validation generator or an iterable, optional): Determines the cross-validation splitting strategy. Defaults to 5.
        n_iters (int, optional): Number of parameter settings that are sampled. Defaults to 100.
        n_jobs (int, optional): Number of jobs to run in parallel. Defaults to 1. (n_jobs=n_cores if on MSI)
        verbose (int, optional): Controls the verbosity. Defaults to 2.
        scoring (string, callable, list/tuple, dict or None, optional): A single string (see The scoring parameter: defining model evaluation rules) or a callable (see Defining your scoring strategy from metric functions) to evaluate the predictions on the test set. Defaults to "neg_mean_absolute_error".
        random_state (int, RandomState instance or None, optional): Controls the randomness of the estimator. Defaults to SEED.
        keep_train_score (bool, optional): If False, the cv_results_ attribute will not include training scores. Defaults to False for memory efficiency.
        filename (string, optional): The name of the file to save the search. Defaults to "rf_reg.pkl".
        save_dir (string, optional): The name of the directory to save the search. Defaults to DATA_DIR.
        save_best (bool, optional): If True, will save the best estimator. Defaults to True.
        best_name (string, optional): The name of the file to save the best estimator. Defaults to "rf_reg_best-estm.pkl".
        remake (bool, optional): If True, will remake the search. Defaults to False.

    Returns:
        sklearn.model_selection._search.GridSearchCV
    """

    if not remake and os.path.exists(os.path.join(save_dir, filename)):
        return joblib.load(os.path.join(save_dir, filename))

    gs = RandomizedSearchCV(
        model,
        param_dists,
        cv=cv,
        n_iter=n_iters,
        n_jobs=n_jobs,
        verbose=verbose,
        scoring=scoring,
        random_state=random_state,
        return_train_score=keep_train_score,
    )
    gs.fit(X_train, Y_train)

    if save_best:
        best_estimator = gs.best_estimator_
        joblib.dump(best_estimator, os.path.join(save_dir, best_name))

    joblib.dump(gs, os.path.join(save_dir, filename))
    return joblib.load(os.path.join(save_dir, filename))


def main():

    tags = ["op", "rc"]

    for tag in tags:

        pkls_subdir = os.path.join(SAVE_DIR, tag + "_steady")

        df_orig = load_csv(filename="ml_data_" + tag + "_steady.csv")
        df_copy = df_orig.copy()

        columns = list(df_copy)
        targets = ["loop-tof"]
        non_features = ["steady-state-condition"]
        features = [f for f in columns if f not in targets + non_features]

        condition = (df_copy["loop-tof"] <= -1e-4) | (df_copy["loop-tof"] >= 1e-4)
        df_filtered = df_copy.loc[condition]

        df = map_target_values(
            df_filtered,
            target="loop-tof",
            new_target_name="log-loop-tof",
            encoding=lambda x: np.log(np.abs(x)),
        )

        X_train, X_test, Y_train, Y_test = split_train_test(
            df,
            target="log-loop-tof",
            features=features,
            test_size=0.10,
            random_state=SEED,
            check_shape=True,
        )

        Y_train, Y_test = Y_train.ravel(), Y_test.ravel()

        model = RandomForestRegressor(
            random_state=SEED,
        )

        cv = KFold(n_splits=10, shuffle=False)
        param_dists = {
            "n_estimators": st.randint(100, 1500, 100),
            "criterion": ["squared_error", "friedman_mse"],
            "max_depth": range(1, 50),
            "min_samples_split": range(2, 20),
            "min_samples_leaf": range(1, 20),
            "max_features": ["sqrt", "log2", None],
        }

        rs = search_random_params(
            X_train,
            Y_train,
            model,
            param_dists,
            cv=cv,
            n_iters=5000,
            n_jobs=128,
            verbose=1,
            scoring="neg_mean_absolute_error",
            keep_train_score=True,
            filename="rf_reg_" + tag + ".pkl",
            save_dir=pkls_subdir,
            save_best=True,
            best_name="rf_reg_" + tag + "-best-estm.pkl",
            remake=True,
        )

    return None


if __name__ == "__main__":
    main()
