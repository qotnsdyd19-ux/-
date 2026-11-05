from pathlib import Path
from streamlit.testing.v1 import AppTest
ROOT=Path(__file__).resolve().parents[1]

def test_app_runs_without_model_and_never_displays_prediction():
    app=AppTest.from_file(str(ROOT/'app.py')).run(timeout=40)
    assert not app.exception
    assert app.title[0].value=='HZO Ferroelectric AI Predictor'
    prediction=[b for b in app.button if b.label=='2Pr 예측 실행 →']
    assert prediction and prediction[0].disabled
    assert any('활성 모델' in i.value or '학습된 모델 없음' in i.value for i in app.info)
    assert any(m.value=='78' for m in app.metric)
    app.text_input[0].set_value('no-such-sample').run(timeout=40)
    assert not app.exception
