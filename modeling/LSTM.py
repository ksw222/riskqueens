import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
from optuna.pruners import MedianPruner
import optuna
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import BorderlineSMOTE
from thr import find_best_threshold

def lstm_run(X_train, y_train, X_test, use_SMOTE) :
    
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)    
    X_train = X_train.reshape((X_train.shape[0], 1, X_train.shape[1]))
    X_test = X_test.reshape((X_test.shape[0], 1, X_test.shape[1]))
    
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    # -----------------------------
    # LSTM 모델 생성 함수
    # -----------------------------
    def create_lstm_model(input_shape, hidden_units, dropout_rate, learning_rate):
        model = Sequential()
        model.add(LSTM(hidden_units, input_shape=input_shape))
        model.add(Dropout(dropout_rate))
        model.add(Dense(1, activation='sigmoid'))
        model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
                    loss='binary_crossentropy')
        return model

    # -----------------------------
    # Optuna 목적 함수
    # -----------------------------
    def objective(trial, X_train, y_train):
        
        hidden_units = trial.suggest_categorical("hidden_units", [34,48,64])
        dropout_rate = trial.suggest_float("dropout_rate", 0.0, 0.5)
        learning_rate = trial.suggest_float("learning_rate", 1e-4, 1e-2, log=True)
        batch_size = trial.suggest_categorical("batch_size", [32,64])
        patience = trial.suggest_int("patience", 3, 10)

        model = create_lstm_model(input_shape=(1, X_train.shape[2]),
                                hidden_units=hidden_units,
                                dropout_rate=dropout_rate,
                                learning_rate=learning_rate)

        # 얼리 스톱핑 콜백
        es = EarlyStopping(monitor='val_loss', mode='min', patience=patience,
                        restore_best_weights=True, verbose=0)

        oof_probs = np.zeros(len(y_train))
        oof_idx = np.zeros(len(y_train), dtype=bool)        
        
        for fold, (tr_idx, val_idx) in enumerate(skf.split(X_train, y_train)):
            X_tr, X_val = X_train[tr_idx], X_train[val_idx]
            y_tr, y_val = y_train.iloc[tr_idx], y_train.iloc[val_idx]
            # 학습
            model.fit(X_tr, y_tr,
                    validation_data=(X_val, y_val),
                    epochs=30,
                    batch_size=batch_size,
                    callbacks=[es],
                    verbose=0)
            
            probs = model.predict(X_val).squeeze()
            
            oof_probs[val_idx] = probs
            oof_idx[val_idx] = True

        # 안전 체크(모든 인덱스가 채워졌는지)
        assert oof_idx.all()

        # OOF 기반으로 최적 threshold 찾기
        best_thr, best_f1 = find_best_threshold(y_train, oof_probs)

        # Optuna는 maximize 하므로 F1 반환
        # (또는 -best_f1을 minimize로 해도 됨)
        trial.set_user_attr("best_threshold", float(best_thr))
        
        return float(best_f1)

    # -----------------------------
    # Optuna 하이퍼파라미터 튜닝
    # -----------------------------
    study = optuna.create_study(direction='maximize', pruner=MedianPruner())
    study.optimize(lambda trial: objective(trial, X_train, y_train), n_trials=5)

    # -----------------------------
    # 최종 모델 학습
    # -----------------------------
    best_params = study.best_params
    best_thr = study.best_trial.user_attrs.get("best_threshold")

    model = create_lstm_model(input_shape=(1, X_train.shape[2]),
                                    hidden_units=best_params['hidden_units'],
                                    dropout_rate=best_params['dropout_rate'],
                                    learning_rate=best_params['learning_rate'])

    es = EarlyStopping(monitor='val_loss', mode='min', patience=best_params['patience'], restore_best_weights=True, verbose=1)
    
    if use_SMOTE :
        smote = BorderlineSMOTE(random_state=42, kind="borderline-1")
        X_train, y_train = smote.fit_resample(X_train, y_train)

    for fold, (tr_idx, val_idx) in enumerate(skf.split(X_train, y_train)):
        X_tr, X_val = X_train[tr_idx], X_train[val_idx]
        y_tr, y_val = y_train.iloc[tr_idx], y_train.iloc[val_idx]
        # 학습
        model.fit(X_tr, y_tr,
                validation_data=(X_val, y_val),
                epochs=30,
                batch_size=best_params['batch_size'],
                callbacks=[es],
                    verbose=1)
    
    y_prob = model.predict(X_test).squeeze()
    y_pred = (y_prob >= best_thr).astype(int)

    return {'best_params' : best_params, 'best_thr' : best_thr, 'y_prob' : y_prob, 'y_pred' : y_pred}
    
    
