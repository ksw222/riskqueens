from catboost import CatBoostClassifier
import optuna
import numpy as np
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import BorderlineSMOTE
from thr import find_best_threshold

def Cat_run(X_train, y_train, X_test, use_SMOTE) : 
    
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)
    # -----------------------------
    # Optuna objective 함수 정의
    # -----------------------------
    def objective(trial):
        # CatBoost 하이퍼파라미터 공간
        params = {
            'iterations': trial.suggest_int('iterations', 500, 3000),
            'depth': trial.suggest_int('depth', 4, 10),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
            'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 1, 10),
            'border_count': trial.suggest_int('border_count', 32, 255),
            'random_strength': trial.suggest_float('random_strength', 1e-9, 10, log=True),
            'bagging_temperature': trial.suggest_float('bagging_temperature', 0.0, 1.0),
            'loss_function': 'Logloss',
            'eval_metric': 'AUC',
            'verbose': 0,
            'random_state': 42,
            'early_stopping_rounds': 100  # 도중 중단 기준
        }
                    
        model = CatBoostClassifier(**params)
        
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        oof_probs = np.zeros(len(y_train))
        oof_idx = np.zeros(len(y_train), dtype=bool)

        for fold, (tr_idx, val_idx) in enumerate(skf.split(X_train, y_train)):
            X_tr, X_val = X_train[tr_idx], X_train[val_idx]
            y_tr, y_val = y_train.iloc[tr_idx], y_train.iloc[val_idx]
                    
            model.fit(X_tr, y_tr)

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

    # -----------------------------
    # 4. Optuna 스터디 생성 및 최적화
    # -----------------------------
    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=5, timeout=3600,  # 시간제한 1시간
                callbacks=[lambda study, trial: study.stop() if study.best_value > 0.9 else None])

    # -----------------------------
    # 최적 하이퍼파라미터 확인
    # -----------------------------
    trial = study.best_trial
    best_params = trial.params
    best_params.update({'loss_function':'Logloss', 'eval_metric':'AUC', 'random_state':42})
    best_thr = study.best_trial.user_attrs.get("best_threshold")
    
    model = CatBoostClassifier(**best_params)

    if use_SMOTE :
        smote = BorderlineSMOTE(random_state=42, kind="borderline-1")
        X_train, y_train = smote.fit_resample(X_train, y_train)

    model.fit(X_train, y_train)
    
    y_prob = model.predict_proba(X_test)[:,1]
    y_pred = (y_prob >= best_thr).astype(int)

    return {'best_params' : best_params, 'best_thr' : best_thr, 'y_prob' : y_prob, 'y_pred' : y_pred}
