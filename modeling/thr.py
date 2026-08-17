from sklearn.metrics import precision_recall_curve
import numpy as np

def find_best_threshold(y_true, probs):
    # precision_recall_curve로 가능한 threshold들 얻기
    precision, recall, thresholds = precision_recall_curve(y_true, probs)
    # thresholds 길이는 precision/recall보다 1 작음 -> compute F1 for each threshold
    # avoid division by zero
    f1_scores = (2 * precision[:-1] * recall[:-1]) / (precision[:-1] + recall[:-1] + 1e-12)
    best_idx = np.argmax(f1_scores)
    best_thr = thresholds[best_idx]
    
    return best_thr, f1_scores[best_idx]