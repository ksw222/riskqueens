import numpy as np
import optuna
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import BorderlineSMOTE
from thr import find_best_threshold

def LR_run(X_train, y_train, X_test, use_SMOTE = False) :

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)
    
    def objective(trial):
        # 하이퍼파라미터 탐색 공간 정의
        C = trial.suggest_loguniform("C", 1e-3, 1e2)  
        
        penalty = trial.suggest_categorical("penalty", ["l1", "l2"])  
        solver = trial.suggest_categorical("solver", ["liblinear", "saga"])  

        # 잘못된 조합이면 trial을 pruning 처리
        if (penalty == "l1" and solver not in ["liblinear", "saga"]) or \
           (penalty == "l2" and solver not in ["liblinear", "saga"]):
            raise optuna.exceptions.TrialPruned()

        model = LogisticRegression(
            C=C, 
            penalty=penalty,
            class_weight="balanced",
            solver=solver,
            max_iter=500,
            random_state=42
        )

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

    # ============================
    # Optuna 실행 (Pruner 적용)
    # ============================
    pruner = optuna.pruners.MedianPruner(n_warmup_steps=2)
    study = optuna.create_study(direction="maximize", pruner=pruner)
    study.optimize(objective, n_trials=5)

    best_params = study.best_params
    best_thr = study.best_trial.user_attrs.get("best_threshold")
    
    model = LogisticRegression(
        **best_params,
        class_weight="balanced",
        max_iter=500,
        random_state=42
    )

    if use_SMOTE :
        smote = BorderlineSMOTE(random_state=42, kind="borderline-1")
        X_train, y_train = smote.fit_resample(X_train, y_train)

    model.fit(X_train, y_train)
    
    y_prob = model.predict_proba(X_test)[:,1]
    y_pred = (y_prob >= best_thr).astype(int)

    return {'best_params' : best_params, 'best_thr' : best_thr, 'y_prob' : y_prob, 'y_pred' : y_pred}


    

