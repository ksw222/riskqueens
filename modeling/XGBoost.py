import xgboost as xgb
import optuna
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import BorderlineSMOTE
from thr import find_best_threshold
import numpy as np

def xg_run(X_train, y_train, X_test, use_SMOTE = False) : 
    
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)
    
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    # Optuna 목적 함수
    def objective(trial, X_train, y_train):
        params = {
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'booster': 'gbtree',
            'lambda': trial.suggest_float('lambda', 1e-3, 10.0, log=True),
            'alpha': trial.suggest_float('alpha', 1e-3, 10.0, log=True),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.3, 1.0),
            'subsample': trial.suggest_float('subsample', 0.3, 1.0),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
            'gamma': trial.suggest_float('gamma', 0, 5),
            'n_estimators': 1000,
            'use_label_encoder': False
        }
        model = xgb.XGBClassifier(**params)

        oof_probs = np.zeros(len(y_train))
        oof_idx = np.zeros(len(y_train), dtype=bool)

        for fold, (tr_idx, val_idx) in enumerate(skf.split(X_train, y_train)):
            X_tr, X_val = X_train[tr_idx], X_train[val_idx]
            y_tr, y_val = y_train.iloc[tr_idx], y_train.iloc[val_idx]
                    
            model.fit(X_tr, y_tr, 
                    eval_set = [(X_val, y_val)],
                    verbose=True
                )

            probs = model.predict_proba(X_val)[:, 1]
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
    
    # Optuna 스터디 생성
    study = optuna.create_study(direction='maximize')
    study.optimize(lambda trial : objective(trial, X_train, y_train), n_trials=5)

    # 최종 모델 학습 (전체 데이터 사용)
    best_params = study.best_params
    best_thr = study.best_trial.user_attrs.get("best_threshold")
    
    model = xgb.XGBClassifier(**best_params)
    
    if use_SMOTE :
        smote = BorderlineSMOTE(random_state=42, kind="borderline-1")
        X_train, y_train = smote.fit_resample(X_train, y_train)
        
    for fold, (tr_idx, val_idx) in enumerate(skf.split(X_train, y_train)):
            X_tr, X_val = X_train[tr_idx], X_train[val_idx]
            y_tr, y_val = y_train.iloc[tr_idx], y_train.iloc[val_idx]
        
            model.fit(X_tr, y_tr, 
                    eval_set = [(X_val, y_val)], 
                    verbose=True
                )

    y_prob = model.predict_proba(X_test)[:,1]
    y_pred = (y_prob >= best_thr).astype(int)

    return {'best_params' : best_params, 'best_thr' : best_thr, 'y_prob' : y_prob, 'y_pred' : y_pred}