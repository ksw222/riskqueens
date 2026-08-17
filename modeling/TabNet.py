import numpy as np
import pandas as pd
from pytorch_tabnet.tab_model import TabNetClassifier
import optuna
import torch
from sklearn.utils import resample
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import BorderlineSMOTE
from thr import find_best_threshold


def tabnet_run(X_train, y_train, X_test, use_SMOTE) :
    
    device_name = "cuda" if torch.cuda.is_available() else "cpu"
    
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # -----------------------------
    # Optuna 목적 함수
    # -----------------------------
    def objective(trial):
        # TabNet 하이퍼파라미터
        params = {
            'n_d': trial.suggest_int('n_d', 16, 32),
            'n_a': trial.suggest_int('n_a', 16, 32),
            'n_steps': trial.suggest_int('n_steps', 3, 5),
            'gamma': trial.suggest_float('gamma', 1.0, 2.0),
            'lambda_sparse': trial.suggest_float('lambda_sparse', 1e-5, 1e-3, log=True),
            'optimizer_fn': torch.optim.Adam,
            'optimizer_params': dict(lr=trial.suggest_float('lr', 1e-4, 1e-2, log=True)),
            'mask_type': trial.suggest_categorical('mask_type', ['sparsemax', 'entmax'])
        }

        model = TabNetClassifier(**params, verbose=0, device_name=device_name)
        
        X,y = resample(X_train, y_train, n_samples=int(0.3*len(X_train)), random_state=42)

        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        oof_probs = np.zeros(len(y))
        oof_idx = np.zeros(len(y), dtype=bool)

        for fold, (tr_idx, val_idx) in enumerate(skf.split(X, y)):
            X_tr, X_val = X[tr_idx], X[val_idx]
            y_tr, y_val = y.iloc[tr_idx], y.iloc[val_idx]
                    
            model.fit(
                X_tr, y_tr,
                max_epochs=30,
                patience=20,
                batch_size=1024,
                virtual_batch_size=128,
                drop_last=False
            )

            probs = model.predict_proba(X_val)[:, 1]
            oof_probs[val_idx] = probs
            oof_idx[val_idx] = True

        # 안전 체크(모든 인덱스가 채워졌는지)
        assert oof_idx.all()

        # OOF 기반으로 최적 threshold 찾기
        best_thr, best_f1 = find_best_threshold(y, oof_probs)

        # Optuna는 maximize 하므로 F1 반환
        # (또는 -best_f1을 minimize로 해도 됨)
        trial.set_user_attr("best_threshold", float(best_thr))
        
        return float(best_f1)
    # -----------------------------
    # Optuna 하이퍼파라미터 튜닝
    # -----------------------------
    study = optuna.create_study(direction='maximize',pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=5))
    study.optimize(lambda trial: objective(trial), n_trials=5)

    # -----------------------------
    # 최종 모델 학습 (전체 데이터)
    # -----------------------------
    best_params = study.best_params
    best_thr = study.best_trial.user_attrs.get("best_threshold")

    model = TabNetClassifier(
        n_d=best_params['n_d'],
        n_a=best_params['n_a'],
        n_steps=best_params['n_steps'],
        gamma=best_params['gamma'],
        lambda_sparse=best_params['lambda_sparse'],
        optimizer_fn=torch.optim.Adam,
        optimizer_params=dict(lr=best_params['lr']),
        mask_type=best_params['mask_type'],
        verbose=1,
        device_name=device_name
    )

    if use_SMOTE :
        smote = BorderlineSMOTE(random_state=42, kind="borderline-1")
        X_train, y_train = smote.fit_resample(X_train, y_train)

    model.fit(
        X_train, y_train,
        max_epochs=30,
        patience=20,
        batch_size=1024,
        virtual_batch_size=128,
        drop_last=False
    )
    
    y_prob = model.predict_proba(X_test)[:,1]
    y_pred = (y_prob >= best_thr).astype(int)

    return {'best_params' : best_params, 'best_thr' : best_thr, 'y_prob' : y_prob, 'y_pred' : y_pred}