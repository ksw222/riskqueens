from sklearn.metrics import (
    average_precision_score, 
    accuracy_score, 
    f1_score, 
    recall_score, 
    precision_score, 
    roc_auc_score
)

def model_result(result, y_test):

    y_prob = result['y_prob']
    y_pred = result['y_pred']
    best_params = result['best_params']
    best_thr = result['best_thr']

    roc_auc = roc_auc_score(y_test, y_prob)
    pr_auc = average_precision_score(y_test, y_prob)
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)

    print("===best params===")
    print(f"best params : {best_params}")
    print(f"best threshold : {best_thr}")
    print("===test result===")
    print(f"accuracy : {accuracy}")
    print(f"precision : {precision}")
    print(f"recall : {recall}")
    print(f"f1 score : {f1}")
    print(f"roc_auc : {roc_auc}")
    print(f"pr_auc : {pr_auc}")
