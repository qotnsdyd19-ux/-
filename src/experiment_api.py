"""Actual supplied-data training/inference service; distinct from verified models."""
from pathlib import Path
import os,secrets,threading
from typing import Literal
from fastapi import FastAPI,HTTPException,Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,ConfigDict,Field
from src.experimental import load,train,predict,CORE

class Inputs(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
    hzo_nm:float=Field(gt=0)
    anneal_c:float=Field(gt=0)
    voltage_v:float|None=Field(default=None,gt=0)
    anneal_s:float|None=Field(default=None,gt=0)
    top:str=Field(min_length=1,max_length=100)
    bottom:str=Field(min_length=1,max_length=100)
    anneal_type:str|None=Field(default=None,max_length=200)
    measurement_state:str|None=Field(default=None,max_length=200)

class Request(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    structure:Literal['MFM']
    target:Literal['2Pr']
    measurement_method:Literal['unconfirmed']
    expected_model_version:str=Field(min_length=1,max_length=100)
    acknowledge_unvalidated:bool=False
    inputs:Inputs

def create_app(root=None):
    root=Path(root or Path(__file__).resolve().parents[1]);lock=threading.Lock()
    app=FastAPI(title='HZO supplied-data experimental training server',version='1',docs_url=None,redoc_url=None)
    app.state.bundle=load(root)
    app.add_middleware(CORSMiddleware,allow_origins=[o.strip() for o in os.environ.get('HZO_CORS_ORIGINS','https://qotnsdyd19-ux.github.io').split(',')],allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['Content-Type','Authorization'])

    @app.get('/healthz')
    @app.get('/readyz')
    def health():return {'ready':True,'mode':'provided_data_experimental','source_review_verified':False,'validation_passed':app.state.bundle['report']['validation_passed']}

    @app.get('/v1/models')
    def models():
        b=app.state.bundle
        return {'models':[{**b['report'],'limits':b['limits'],'categories':b['categories'],'missing_allowed':b['missing_allowed'],'electrode_pairs':b['pairs']}],'source_review_verified':False}

    @app.post('/v1/predict')
    def infer(request:Request):
        bundle=app.state.bundle
        if request.expected_model_version!=bundle['report']['version']:raise HTTPException(409,'모델 버전 변경: 새로고침하세요.')
        try:return predict(bundle,request.inputs.model_dump(),request.acknowledge_unvalidated)
        except ValueError as exc:raise HTTPException(422,str(exc))

    @app.post('/v1/train')
    def retrain(authorization:str|None=Header(default=None)):
        token=os.environ.get('HZO_TRAIN_TOKEN')
        supplied=authorization or ''
        if not token or not supplied.isascii() or not secrets.compare_digest(supplied, 'Bearer '+token):raise HTTPException(403,'학습은 서버 관리자의 인증이 필요합니다.')
        if not lock.acquire(blocking=False):raise HTTPException(409,'이미 학습 중입니다.')
        try:
            bundle,cases=train(root);app.state.bundle=bundle
            return {'report':bundle['report'],'actual_input_results':cases}
        except ValueError as exc:raise HTTPException(422,str(exc))
        finally:lock.release()
    return app

app=create_app()
