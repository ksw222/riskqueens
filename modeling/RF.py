import numpy as np
import optuna
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import BorderlineSMOTE
from sklearn.utils import resample
from thr import find_best_threshold

def RF_run(X_train, y_train, X_test, use_SMOTE = False) :
    
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)
        
    # 조기 종료용 콜백
    class EarlyStoppingCallback:
        def __init__(self, patience=10):
            self.patience = patience
            self.best_score = -np.inf
            self.counter = 0

        def __call__(self, study, trial):
            if study.best_value is not None:
                if study.best_value > self.best_score:
                    self.best_score = study.best_value
                    self.counter = 0
                else:
                    self.counter += 1
            if self.counter >= self.patience:
                study.stop()

    # Optuna objective 함수
    def objective(trial):
        # 하이퍼파라미터 탐색
        n_estimators = trial.suggest_int('n_estimators', 100, 300)
        max_depth = trial.suggest_int('max_depth', 5, 15)
        min_samples_split = trial.suggest_int('min_samples_split', 2, 10)
        min_samples_leaf = trial.suggest_int('min_samples_leaf', 1, 10)
        max_features = trial.suggest_categorical('max_features', ['sqrt', 'log2', None])

        model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            max_features=max_features,
            class_weight='balanced',  # 클래스 불균형 고려
            random_state=42,
            n_jobs=-1
        )
        
        X_train_sub, y_train_sub = resample(X_train, y_train, n_samples=int(0.3*len(X_train)), random_state=42)
      
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        oof_probs = np.zeros(len(y_train_sub))
        oof_idx = np.zeros(len(y_train_sub), dtype=bool)

        for fold, (tr_idx, val_idx) in enumerate(skf.split(X_train_sub, y_train_sub)):
            X_tr, X_val = X_train_sub[tr_idx], X_train_sub[val_idx]
            y_tr, y_val = y_train_sub.iloc[tr_idx], y_train_sub.iloc[val_idx]
                    
            model.fit(X_tr, y_tr)

            probs = model.predict_proba(X_val)[:, 1]
            oof_probs[val_idx] = probs
            oof_idx[val_idx] = True

        # 안전 체크(모든 인덱스가 채워졌는지)
        assert oof_idx.all()

        # OOF 기반으로 최적 threshold 찾기
        best_thr, best_f1 = find_best_threshold(y_train_sub, oof_probs)

        # Optuna는 maximize 하므로 F1 반환
        # (또는 -best_f1을 minimize로 해도 됨)
        trial.set_user_attr("best_threshold", float(best_thr))
        
        return float(best_f1)


    # Optuna 스터디 생성
    study = optuna.create_study(direction='maximize')
    early_stopping = EarlyStoppingCallback(patience=10)
    study.optimize(objective, n_trials=5, callbacks=[early_stopping])

    # 최적 결과 출력
    trial = study.best_trial
    best_params = trial.params
    best_thr = study.best_trial.user_attrs.get("best_threshold")
    
    # 최적 하이퍼파라미터로 모델 학습
    model = RandomForestClassifier(
        n_estimators=trial.params['n_estimators'],
        max_depth=trial.params['max_depth'],
        min_samples_split=trial.params['min_samples_split'],
        min_samples_leaf=trial.params['min_samples_leaf'],
        max_features=trial.params['max_features'],
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    
    if use_SMOTE :
            smote = BorderlineSMOTE(random_state=42, kind="borderline-1")
            X_train, y_train = smote.fit_resample(X_train, y_train)

    model.fit(X_train, y_train)
    
    y_prob = model.predict_proba(X_test)[:,1]
    y_pred = (y_prob >= best_thr).astype(int)

    return {'best_params' : best_params, 'best_thr' : best_thr, 'y_prob' : y_prob, 'y_pred' : y_pred}
