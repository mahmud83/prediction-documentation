# numpy and pandas for data manipulation
import pandas as pd
import numpy as np

# Sklearn preprocessing functionality
from sklearn.preprocessing import LabelEncoder, MinMaxScaler

# Models from Sklearn
from sklearn.linear_model import ElasticNet
from sklearn.neighbors import KNeighborsRegressor
from sklearn.svm import SVR
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, AdaBoostRegressor

# Timing utilities
from timeit import default_timer as timer


def preprocess_data(df, test_days = 183, scale = True):
    """Preprocess a building energy dataframe for machine learning models. 
    
    Parameters:
    ------
    
    df : dataframe
        Building energy dataframe with each row containing one observation
        and the columns holding the features. The dataframe must contain the 
        "elec_cons" column to be used as the target.
    
    test_days : integer (default = 183)
        Number of testing days used for splitting into training and testing sets.
        The most recent test_days will be in the testing set while the rest of the data
        will be used for training.
        
    scale : boolean (default = True)
        Indicator for whether or not the features should be scaled. If True, 
        the features are scaled the range of 0 to 1.
        
    Return:
    ______
    
    train : dataframe, shape = [n_training_samples, n_features]
        Set of training features for training a model
    
    train_targets : array, shape = [n_training_samples]
        Array of training targets for training a model
        
    test : dataframe, shape = [n_testing_samples, n_features]
        Set of testing features for making predictions with a model
    
    test_targets : array, shape = [n_testing_samples]
        Array of testing targets for evaluating the model predictions
        
    """
    
    # Fill in NaN values 
    df['sun_rise_set'] = df['sun_rise_set'].fillna('neither')
    
    # Convert to a datetime index
    df['timestamp'] = pd.DatetimeIndex(df['timestamp'])

    # Create new time features
    df['yday'] = df['timestamp'].dt.dayofyear
    df['month'] = df['timestamp'].dt.month
    df['wday'] = df['timestamp'].dt.dayofweek
    
    cyc_features = ['yday', 'month', 'wday', 'num_time'] 

    # Iterate through the variables
    for feature in cyc_features:
        df['%s_sin' % feature] = np.sin(2 * np.pi * df[feature] / df[feature].max())
        df['%s_cos' % feature] = np.cos(2 * np.pi * df[feature] / df[feature].max())
        
    # Remove the ordered time features
    df = df.drop(columns = ['yday', 'month', 'wday', 'num_time', 'day_of_week'])
    
    # Convert the timestamp to total seconds since beginning of data
    df['timestamp'] = (df['timestamp'] - df['timestamp'].min()).dt.total_seconds()
    
    label_encoder = LabelEncoder()

    # Label encode
    df['week_day_end'] = label_encoder.fit_transform(df['week_day_end'])

    # One hot encode
    df = pd.get_dummies(df)
    
    # Remove observations 0 or less
    df = df[df['elec_cons'] > 0]

    # Select the targets 
    targets = np.array(df['elec_cons']).reshape((-1, ))

    columns_remove = ['elec_cons', 'elec_cons_imp', 'pow_dem', 'anom_flag', 'anom_missed_flag', 'cleaned_energy', 'forecast']

    # Remove the columns only if present in dataframe
    df = df.drop(columns = [x for x in columns_remove if x in df.columns])
    
    index = 0
    frequency = 0

    # Check to make sure that timestamps are not repeated
    while frequency < 1:
        frequency = df['timestamp'][index + 1] - df['timestamp'][index]

        # Make sure to increment index
        index += 1

    # Observations per day
    daily_observations = (60 * 60 * 24) / frequency

    # Start of test period
    test_start = int(len(df) - test_days * daily_observations)
    
    # Select the training and testing features
    train, test = df.iloc[:test_start], df.iloc[test_start:]

    # Select the training and testing targets
    train_targets, test_targets = targets[:test_start], targets[test_start:]

    
    if scale:
        # Create the scaler object with a specified range
        scaler = MinMaxScaler(feature_range = (0, 1))

        # Fit on the training data
        scaler.fit(train)

        # Transform both the training and testing data
        train = scaler.transform(train)
        test = scaler.transform(test)

        features = list(df.columns)

        # Convert back to dataframes
        train = pd.DataFrame(train, columns=features)
        test = pd.DataFrame(test, columns=features)
    
    # Check for missing values
    assert ~np.any(train.isnull()), "Training Data Contains Missing Values!"
    assert ~np.any(test.isnull()), "Testing Data Contains Missing Values!"
    
    return train, train_targets, test, test_targets


def evaluate_models(df):
    """Evaluate scikit-learn machine learning models
    on a building energy dataset. More models can be added
    to the function as required. 
    
    
    Parameters
    --------
    df : dataframe
        Building energy dataframe. Each row must have one observation
        and the columns must contain the features. The dataframe
        needs to have an "elec_cons" column to be used as targets. 
    
    Return
    --------
    results : dataframe, shape = [n_models, 4]
        Modeling metrics. A dataframe with columns:
        model, train_time, test_time, mape. Used for comparing
        models for a given building dataset
        
    """
    try:
        # Preprocess the data for machine learning
        train, train_targets, test, test_targets = preprocess_data(df, test_days = 183, scale = True)
    except Exception as e:
        print('Error processing data: ', e)
        return
        
    # elasticnet
    model = ElasticNet(alpha = 1.0, l1_ratio=0.5)
    elasticnet_results = implement_model(model, train, train_targets, test, 
                                         test_targets, model_name = 'elasticnet')
    
    # knn
    model = KNeighborsRegressor()
    knn_results = implement_model(model, train, train_targets, test, 
                                  test_targets, model_name = 'knn')
    
    # svm
    model = SVR()
    svm_results = implement_model(model, train, train_targets, test, 
                                   test_targets, model_name = 'svm')
    
    # rf
    model = RandomForestRegressor(n_estimators = 100, n_jobs = -1)
    rf_results = implement_model(model, train, train_targets, test, 
                                  test_targets, model_name = 'rf')
    
    # et
    model = ExtraTreesRegressor(n_estimators=100, n_jobs = -1)
    et_results = implement_model(model, train, train_targets, test, 
                                  test_targets, model_name = 'et')
    
    # adaboost
    model = AdaBoostRegressor(n_estimators = 1000, learning_rate = 0.05, 
                              loss = 'exponential')
    adaboost_results = implement_model(model, train, train_targets, test, 
                                       test_targets, model_name = 'adaboost')
    
    # Put the results into a single array (stack the rows)
    results = np.vstack((elasticnet_results, knn_results, svm_results,
                         rf_results, et_results, adaboost_results))
    
    # Convert the results to a dataframe
    results = pd.DataFrame(results, columns = ['model', 'train_time', 'test_time', 'mape'])
    
    # Convert the numeric results to numbers
    results.iloc[:, 1:] = results.iloc[:, 1:].astype(np.float32)
    
    return results