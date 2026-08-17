import pandas as pd
import warnings
from result import model_result

warnings.filterwarnings('ignore')

# 데이터 선택
data_select = input("데이터를 선택하세요(상장/비상장/ALL) : ")
data_select = data_select.upper()

if data_select in ['상장', '비상장', 'ALL'] :
    df = pd.read_csv(f'data/{data_select}.csv')
else :
    raise ValueError ("데이터를 잘못 선택했습니다.")

feature_selection = input(
    """피처 셀렉션 방법을 선택하세요.
    1: Elastic Net
    2: PCA
    """
)
if feature_selection == '1' :
    print("피처 셀렉션 방법 : Elastic Net")
    if data_select == '상장' :
        feature_cols = [
            'ROA',
            '영업이익률',
            '부채 대비 영업활동으로 인한 현금흐름',
            'LVGI',
            '총자산회전율',
            '부채 대비 재무활동으로 인한 현금흐름',
            'TATA',
            'PBR',
            'Volume',
            '매출총이익률',
            '자기자본증가율',
            'SGI',
            '유형자산회전율',
            '금융비용부담률',
            '총자산증가율' 
        ]
    elif data_select == '비상장' :
        feature_cols = [
            'GMI',
            'ROA',
            'LVGI',
            '총자산회전율',
            '부채 대비 영업활동으로 인한 현금흐름',
            '부채 대비 재무활동으로 인한 현금흐름',
            '이익잉여금',
            '금융비용부담률',
            '영업외수익',
            '투자활동으로 인한 현금흐름',
            '이자보상배율',
            '종업원',
            '매출채권회전율',
            '재고자산',
            '매출채권'
        ]
    elif data_select == 'ALL' :
        feature_cols = [
            'GMI',
            'ROA',
            'LVGI',
            '총자산회전율',
            '부채 대비 영업활동으로 인한 현금흐름',
            '부채 대비 재무활동으로 인한 현금흐름',
            '이자보상배율',
            '금융비용부담률',
            '매출채권회전율',
            '자본잉여금',
            '유형자산회전율',
            '감가상각비',
            '유형자산증가율',
            '기타포괄손익누계액'
        ]

elif feature_selection == '2' :
    print("피처 셀렉션 방법 : PCA")    
    if data_select == '상장' :        
        feature_cols = ['감가상각비', 
                        'Marcap', 
                        '매출총이익률', 
                        'LVGI', 
                        'SGI', 
                        'AQI', 
                        '유동비율', 
                        '부채 대비 영업활동으로 인한 현금흐름', 
                        '총자산회전율', 
                        '부채 대비 투자활동으로 인한 현금흐름', 
                        '기타포괄손익누계액', 
                        '장기차입금', 
                        '재무활동으로 인한 현금흐름', 
                        '종업원'
                    ]
    elif data_select == '비상장' :
        feature_cols = ['매출채권회전율',
                        '매출채권',
                        '이자보상배율',
                        '재무활동으로 인한 현금흐름',
                        '영업활동으로 인한 현금흐름',
                        '유형자산',
                        '영업외비용',
                        '이자비용',
                        '자본금',
                        '금융비용부담률',
                        '재고자산',
                        '종업원',
                        '판매비와관리비',
                        '감가상각비',
                        '이익잉여금'
                    ]
    elif data_select == 'ALL' :
        feature_cols = ['매출채권회전율',
                        '금융비용부담률',
                        '총자산회전율',
                        '부채 대비 영업활동으로 인한 현금흐름',
                        '유형자산회전율'
                    ]
else :
    raise ValueError ("피처 셀렉션 방법을 잘못 선택했습니다.")

X_train = df.loc[df['회계년도'] <= '2017/12', feature_cols]
X_test = df.loc[df['회계년도'] > '2017/12', feature_cols]
y_train = df.loc[df['회계년도'] <= '2017/12', 'label']
y_test = df.loc[df['회계년도'] > '2017/12', 'label']

# smote 사용 여부 선택
use_smote = input("smote를 진행할까요?(Y/N) : ")
use_smote = use_smote.upper()

if use_smote == 'Y' :
    print("smote를 진행합니다.")
    use_SMOTE = True
elif use_smote == 'N' :
    print("smote를 진행하지 않습니다.")
    use_SMOTE = False
else :
    print("선택이 잘못되었습니다. 기본적으로 smote 없이 진행합니다.")
    use_SMOTE = False

# 모델 선택
model_select = input(
    """
        모델을 선택하세요.
        1 : 로지스틱회귀모형 
        2 : RandomForest
        3 : CatBoost
        4 : XGBoost
        5 : LSTM 
        6 : TabNet
    """
)

if model_select == '1' :
    print("모델 선택 : 로지스틱회귀모형")
    from LR import LR_run
    result = LR_run(X_train, y_train, X_test, use_SMOTE)
elif model_select == '2' :
    print("모델 선택 : RandomForest")
    from RF import RF_run
    result = RF_run(X_train, y_train, X_test, use_SMOTE)
elif model_select == '3' :
    print("모델 선택 : CatBoost")
    from CatBoost import Cat_run
    result = Cat_run(X_train, y_train, X_test, use_SMOTE)
elif model_select == '4' :
    print("모델 선택 : XGBoost")
    from XGBoost import xg_run
    result = xg_run(X_train, y_train, X_test, use_SMOTE)
elif model_select == '5' :
    print("모델 선택 : LSTM")
    from LSTM import lstm_run
    result = lstm_run(X_train, y_train, X_test, use_SMOTE)
elif model_select == '6' :
    print("모델 선택 : TabNet")
    from TabNet import tabnet_run
    result = tabnet_run(X_train, y_train, X_test, use_SMOTE)
else :
    raise ValueError ("숫자를 잘못 선택했습니다.")

model_result(result, y_test)