"""Public inference API. No upload, approval, model loading or training routes."""
import os
from pathlib import Path
from typing import Literal
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from src.model import predict
from src.serving import Registry

class Inputs(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
    hzo_nm:float=Field(gt=0)
    top_nm:float|None=Field(default=None,gt=0)
    bottom_nm:float|None=Field(default=None,gt=0)
    anneal_c:float=Field(gt=0)
    anneal_s:float|None=Field(default=None,gt=0)
    voltage_v:float=Field(gt=0)
    wake_cycles:float|None=Field(default=None,ge=0)
    top:str=Field(min_length=1,max_length=100)
    bottom:str=Field(min_length=1,max_length=100)
    atmosphere:str|None=Field(default=None,min_length=1,max_length=100)
    measurement_method:Literal['P-E','PUND']
    measurement_state:str=Field(min_length=1,max_length=100)
    deposition:str|None=Field(default=None,min_length=1,max_length=100)
    ald_c:float|None=None
    pulse_s:float|None=Field(default=None,gt=0)
    frequency_hz:float|None=Field(default=None,gt=0)
    multilayer:bool=False
    top_interlayer_nm:float=Field(default=0,ge=0)
    bottom_interlayer_nm:float=Field(default=0,ge=0)

class Request(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    structure:Literal['MFM','MFIS']
    target:Literal['2Pr','Memory Window','Threshold shift','Endurance']
    expected_model_version:str=Field(min_length=1,max_length=100)
    inputs:Inputs

def create_app(model_dir=None,data_root=None,allow_test_fixtures=False):
    registry=Registry(model_dir or os.environ.get('HZO_MODEL_DIR',Path(__file__).resolve().parents[1]/'models'),source_root=data_root,allow_test_fixtures=allow_test_fixtures)
    app=FastAPI(title='HZO verified inference',version='2.1',docs_url=None,redoc_url=None)
    app.state.registry=registry
    origins=os.environ.get('HZO_CORS_ORIGINS','https://qotnsdyd19-ux.github.io').split(',')
    app.add_middleware(CORSMiddleware,allow_origins=[o.strip() for o in origins if o.strip()],allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['Content-Type'])

    @app.get('/healthz')
    def health():return {'service':'hzo-inference','status':'running','ready':bool(registry.bundles),'active_models':len(registry.bundles)}

    @app.get('/readyz')
    def ready():
        if not registry.bundles:return JSONResponse(status_code=503,content={'ready':False,'reasons':registry.problems})
        return {'ready':True}

    @app.get('/v1/models')
    def models():return {'models':registry.metadata(),'prediction_available':bool(registry.bundles),'reasons':registry.problems}

    @app.post('/v1/predict')
    def infer(request:Request):
        key=(request.structure,request.target,request.inputs.measurement_method)
        bundle=registry.bundles.get(key)
        if bundle is None:raise HTTPException(503,detail='선택한 구조·측정 방법·출력의 검증된 모델이 없습니다.')
        report=bundle['report']
        if request.expected_model_version!=report['version']:raise HTTPException(409,detail='모델 버전이 바뀌었습니다. 모델 정보를 새로 불러오세요.')
        inputs=request.inputs.model_dump()
        inputs['multilayer']=inputs['multilayer'] or inputs['top_interlayer_nm']>0 or inputs['bottom_interlayer_nm']>0
        value,issues=predict(bundle,inputs)
        if value is None:raise HTTPException(422,detail=issues)
        return {'kind':'model_prediction','structure':request.structure,'target':request.target,'value':value,'unit':report['unit'],
                'model_version':report['version'],'dataset_hash':report['dataset_hash'],'inputs':inputs,
                'validation':report['forest'],'limitations':report['limitations']}
    return app

app=create_app()
