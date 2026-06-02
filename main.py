from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Text, Enum
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil

SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:@localhost:3306/ats_sistema"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class DBVacante(Base):
    __tablename__ = "vacantes"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=False)
    estado = Column(Enum('Abierta', 'Pausada', 'Cerrada'), default='Abierta')
    id_creador = Column(Integer, nullable=False)


class DBCandidato(Base):
    __tablename__ = "candidatos"
    id = Column(Integer, primary_key=True, index=True)
    nombre_completo = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True)
    telefono = Column(String(20))
    origen = Column(Enum('Correo', 'WhatsApp', 'Impreso',
                    'Portal Web', 'Referido'), nullable=False)
    url_cv = Column(String(255))
    estado = Column(String(50), default="Recibido")
    historial = Column(Text, default="CV Registrado en MySQL")
    id_vacante = Column(Integer, nullable=True)
    habilidades = Column(Text, nullable=True)


class DBCuestionario(Base):
    __tablename__ = "cuestionarios"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(100), nullable=False)
    preguntas = Column(Text, nullable=False)


class VacanteCreate(BaseModel):
    titulo: str
    descripcion: str
    estado: Optional[str] = "Abierta"
    id_creador: int


class VacanteResponse(VacanteCreate):
    id: int

    class Config:
        from_attributes = True


class CandidatoResponse(BaseModel):
    id: int
    nombre_completo: str
    email: str
    origen: str
    url_cv: Optional[str] = None
    habilidades: Optional[str] = None
    id_vacante: Optional[int] = None
    estado: Optional[str] = "Recibido"
    historial: Optional[str] = "CV Registrado en MySQL"

    class Config:
        from_attributes = True


class CandidatoEvaluacion(BaseModel):
    estado: str
    comentarios: str


class CuestionarioCreate(BaseModel):
    titulo: str
    preguntas: str


class CuestionarioResponse(CuestionarioCreate):
    id: int

    class Config:
        from_attributes = True


app = FastAPI(
    title="API Sistema ATS",
    description="Backend para la automatización de reclutamiento y selección.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def read_root():
    return {"mensaje": "Bienvenido a la API del Sistema ATS."}


@app.post("/vacantes/", response_model=VacanteResponse, tags=["Vacantes"])
def crear_vacante(vacante: VacanteCreate, db: Session = Depends(get_db)):
    db_vacante = DBVacante(**vacante.model_dump())
    db.add(db_vacante)
    db.commit()
    db.refresh(db_vacante)
    return db_vacante


@app.get("/vacantes/", response_model=List[VacanteResponse], tags=["Vacantes"])
def listar_vacantes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    vacantes = db.query(DBVacante).offset(skip).limit(limit).all()
    return vacantes


@app.put("/vacantes/{vacante_id}", response_model=VacanteResponse, tags=["Vacantes"])
def actualizar_vacante(vacante_id: int, vacante_actualizada: VacanteCreate, db: Session = Depends(get_db)):
    vacante = db.query(DBVacante).filter(DBVacante.id == vacante_id).first()
    if not vacante:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")

    vacante.titulo = vacante_actualizada.titulo
    vacante.descripcion = vacante_actualizada.descripcion
    vacante.estado = vacante_actualizada.estado

    db.commit()
    db.refresh(vacante)
    return vacante


@app.delete("/vacantes/{vacante_id}", tags=["Vacantes"])
def eliminar_vacante(vacante_id: int, db: Session = Depends(get_db)):
    vacante = db.query(DBVacante).filter(DBVacante.id == vacante_id).first()
    if not vacante:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")
    db.delete(vacante)
    db.commit()
    return {"mensaje": "Vacante eliminada exitosamente"}


@app.post("/candidatos/", response_model=CandidatoResponse, tags=["Candidatos"])
def registrar_candidato(
    nombre_completo: str = Form(...),
    email: str = Form(...),
    origen: str = Form(...),
    habilidades: Optional[str] = Form(None),
    id_vacante: Optional[int] = Form(None),
    cv: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    db_candidato = db.query(DBCandidato).filter(
        DBCandidato.email == email).first()
    if db_candidato:
        raise HTTPException(
            status_code=400, detail="El email ya está registrado")

    ruta_archivo = None
    if cv and cv.filename:
        nombre_archivo = cv.filename.replace(" ", "_")
        ruta_fisica = f"uploads/{nombre_archivo}"
        with open(ruta_fisica, "wb") as buffer:
            shutil.copyfileobj(cv.file, buffer)
        ruta_archivo = f"/{ruta_fisica}"

    habs_limpias = habilidades if habilidades else ""

    nuevo_candidato = DBCandidato(
        nombre_completo=nombre_completo,
        email=email,
        origen=origen,
        url_cv=ruta_archivo,
        habilidades=habs_limpias,
        id_vacante=id_vacante
    )
    db.add(nuevo_candidato)
    db.commit()
    db.refresh(nuevo_candidato)
    return nuevo_candidato


@app.put("/candidatos/{candidato_id}", response_model=CandidatoResponse, tags=["Candidatos"])
def actualizar_candidato(
    candidato_id: int,
    nombre_completo: str = Form(...),
    email: str = Form(...),
    origen: str = Form(...),
    habilidades: Optional[str] = Form(None),
    id_vacante: Optional[int] = Form(None),
    cv: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    candidato = db.query(DBCandidato).filter(
        DBCandidato.id == candidato_id).first()
    if not candidato:
        raise HTTPException(status_code=404, detail="Candidato no encontrado")

    if candidato.email != email:
        email_existente = db.query(DBCandidato).filter(
            DBCandidato.email == email).first()
        if email_existente:
            raise HTTPException(
                status_code=400, detail="El nuevo email ya está registrado por otro candidato")

    candidato.nombre_completo = nombre_completo
    candidato.email = email
    candidato.origen = origen
    candidato.habilidades = habilidades if habilidades else ""
    candidato.id_vacante = id_vacante

    if cv and cv.filename:
        nombre_archivo = cv.filename.replace(" ", "_")
        ruta_fisica = f"uploads/{nombre_archivo}"
        with open(ruta_fisica, "wb") as buffer:
            shutil.copyfileobj(cv.file, buffer)
        candidato.url_cv = f"/{ruta_fisica}"

    db.commit()
    db.refresh(candidato)
    return candidato


@app.get("/candidatos/", response_model=List[CandidatoResponse], tags=["Candidatos"])
def listar_candidatos(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    candidatos = db.query(DBCandidato).offset(skip).limit(limit).all()
    return candidatos


@app.delete("/candidatos/{candidato_id}", tags=["Candidatos"])
def eliminar_candidato(candidato_id: int, db: Session = Depends(get_db)):
    candidato = db.query(DBCandidato).filter(
        DBCandidato.id == candidato_id).first()
    if not candidato:
        raise HTTPException(status_code=404, detail="Candidato no encontrado")
    db.delete(candidato)
    db.commit()
    return {"mensaje": "Candidato eliminado exitosamente"}


@app.put("/candidatos/{candidato_id}/evaluar", tags=["Candidatos"])
def evaluar_candidato(candidato_id: int, eval_data: CandidatoEvaluacion, db: Session = Depends(get_db)):
    candidato = db.query(DBCandidato).filter(
        DBCandidato.id == candidato_id).first()
    if not candidato:
        raise HTTPException(status_code=404, detail="Candidato no encontrado")

    candidato.estado = eval_data.estado
    historial_previo = candidato.historial if candidato.historial else ""
    nuevo_registro = f"| Evaluado ({eval_data.estado}): {eval_data.comentarios}"
    candidato.historial = historial_previo + nuevo_registro

    db.commit()
    db.refresh(candidato)
    return candidato


@app.post("/cuestionarios/", response_model=CuestionarioResponse, tags=["Cuestionarios"])
def crear_cuestionario(cuestionario: CuestionarioCreate, db: Session = Depends(get_db)):
    db_cuestionario = DBCuestionario(
        titulo=cuestionario.titulo, preguntas=cuestionario.preguntas)
    db.add(db_cuestionario)
    db.commit()
    db.refresh(db_cuestionario)
    return db_cuestionario


@app.get("/cuestionarios/", response_model=List[CuestionarioResponse], tags=["Cuestionarios"])
def listar_cuestionarios(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    cuestionarios = db.query(DBCuestionario).offset(skip).limit(limit).all()
    return cuestionarios


@app.delete("/cuestionarios/{cuestionario_id}", tags=["Cuestionarios"])
def eliminar_cuestionario(cuestionario_id: int, db: Session = Depends(get_db)):
    cuestionario = db.query(DBCuestionario).filter(
        DBCuestionario.id == cuestionario_id).first()
    if not cuestionario:
        raise HTTPException(
            status_code=404, detail="Cuestionario no encontrado")
    db.delete(cuestionario)
    db.commit()
    return {"mensaje": "Cuestionario eliminado exitosamente"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
