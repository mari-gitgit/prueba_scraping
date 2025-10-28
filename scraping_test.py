#Importamos librerías
import os
from urllib.parse import urljoin
from zoneinfo import reset_tzpath

import requests #para hacer las peticiones
from bs4 import BeautifulSoup #para realizar el scraping
import pytesseract as pyt #Para superar el captcha
import cv2 #guardar el captcha
import time
from PIL import Image,ImageFilter,ImageOps,ImageEnhance
import numpy as np
from scipy.ndimage import gaussian_filter
import pdfplumber

OUT_PDF = "cedula_resultado.pdf"
def save_pdf_from_response(post_resp, out_pdf_path):
    """
    Guarda el contenido de la respuesta HTTP en out_pdf_path si es PDF.
    post_resp puede ser un requests.Response o bytes si ya descargaste a disco.
    """
    content=None
    # Si es requests.Response
    if hasattr(post_resp,"headers"):
        content_type=post_resp.headers.get("Content-Type","").lower()
        if "application/pdf" in content_type or post_resp.content[:4]==b"%PDF":
            content=post_resp.content
        else:
            # A veces no indica header pero sí es PDF
            if post_resp.content[:4]==b"%PDF":
                content=post_resp.content
    elif isinstance(post_resp,(bytes, bytearray)):
        if post_resp[:4]==b"%PDF":
            content=post_resp
    else:
        raise ValueError("post_resp debe ser requests.Response o bytes del PDF")

    if content is None:
        raise RuntimeError("La respuesta no contiene un PDF válido.")

    # Guardar el PDF
        os.makedirs(os.path.dirname(out_pdf_path) or ".", exist_ok=True)
        with open(out_pdf_path,"wb") as f:
            f.write(content)
        return out_pdf_path

def extract_text_from_pdf(pdf_path):
    """
    Extrae texto concatenado de todas las páginas del PDF usando pdfplumber.
    """
    text=""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text=page.extract_text()
            if page_text:
                text+=page_text + "\n"
    return text

def parse_fields_from_text(text):
    """
    Ajusta estas expresiones regulares según el formato exacto del PDF.
    Retorna un dict con cedula, fecha_expedicion, estado_vigencia (si se encuentran).
    """
    parsed={}

    # Normalizar texto: eliminar dobles espacios y unificar saltos
    t=re.sub(r"[ \t]+"," ",text)
    t=re.sub(r"\n{2,}","\n",t)

    # Patrón cédula: buscar números largos (6-12 dígitos). Ajusta si hay separadores.
    m=re.search(r"\b([0-9]{6,13})\b", t)
    if m:
        parsed["numero_documento"]=m.group(1)

    # Patrón fecha (varios formatos comunes: dd/mm/yyyy, d/m/yyyy, yyyy-mm-dd)
    m=re.search(r"Fecha(?: de expedici[oó]n|:)?\s*[:\-]?\s*([0-3]?\d[\/\-\.\s][01]?\d[\/\-\.\s]\d{4})",t,flags=re.IGNORECASE)
    if not m:
        # alternativa: buscar dd/mm/yyyy en cualquier lugar
        m=re.search(r"\b([0-3]?\d[\/\-\.\s][01]?\d[\/\-\.\s]\d{4})\b", t)
    if m:
        parsed["fecha_expedicion"]=m.group(1).strip()

    # Patrón estado de vigencia: buscar palabras como "Vigente", "No Vigente", "Suspendido", etc.
    m = re.search(r"\b(Vigente|No Vigente|Cancelad[oa]|Suspendid[oa]|Anulado|Activo|Inactivo)\b",t,flags=re.IGNORECASE)
    if m:
        parsed["estado_vigencia"]=m.group(1).strip()

    # Guardar texto crudo parcial para referencia (opcional)
    parsed["raw_text_snippet"] = "\n".join([line.strip() for line in t.splitlines()[:10]])

    return parsed

def save_json(data_dict, out_json_path):
    os.makedirs(os.path.dirname(out_json_path) or ".", exist_ok=True)
    with open(out_json_path,"w",encoding="utf-8") as f:
        json.dump(data_dict,f,ensure_ascii=False,indent=2)
    return out_json_path

#Obtener el HTML
url="https://certvigenciacedula.registraduria.gov.co/Datos.aspx"
client=requests.Session() #Abrir la sesión
pedido=requests.get(url) #Ir a la URL
html_obtenido=pedido.text #Obtener HTML

#Parseo del HTML
soup=BeautifulSoup(html_obtenido,"html.parser")

#Se traen los token por el tipo de página

def find_tok(name):
    tok=soup.find("input",{"id":name})
    return tok.get("value") if tok and tok.has_attr("value") else ""

tokens = {
        "__VIEWSTATE": find_tok("__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": find_tok("__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": find_tok("__EVENTVALIDATION"),
    }

#Hallar el Captcha
id_captcha="datos_contentplaceholder1_captcha1_CaptchaImage"
captcha_element=soup.find(id=id_captcha)
#Se intenta buscar la imagen con ese id
if not captcha_element:
    captcha_element=soup.find('img',id=id_captcha)
if captcha_element and captcha_element.get('src'):
    src=captcha_element.get('src')
    #Se crea la URL absoluta
    if src.startswith('/'):
        captcha_url=urljoin(url,src)
    elif src.startswith('http'):
        captcha_url=src
    else:
        captcha_url=urljoin(url,src)

    try:
        #Descargar la imagen para mejor análisis
        img_response=client.get(captcha_url)
        print(img_response)
        if img_response.status_code == 200:
            timestamp=int(time.time())
            nombre_img=f"captcha_{id_captcha}_{timestamp}.jpg"
            ruta=os.path.join(r"nombre ruta",nombre_img) #Cambiar por nombre de la carpeta o ruta correcta
            print(ruta)

            with open(ruta,'wb') as f:
                f.write(img_response.content)

            print(f"Se guardó imagen CAPTCHA")
        else:
            print(f"Error HTTP {img_response.status_code} al guardar CAPTCHA")
    except Exception as e:
        print(f"Error descargando captcha: {e}")
else:
    print(f"No se encontró CAPTCHA")

#Se procesa la imagen del captcha

def verificar_ruta(ruta):
    #Verificamos que exista
    if not os.path.exists(ruta):
        print("Archivo no existe")
        return False
    tamaño=os.path.getsize(ruta)
    if tamaño==0:
        print("Archivo no existe")
        return False
    if not os.access(ruta,os.R_OK):
        print("No hay permisos")
        return False
    #Intentamos abrir con PIL
    try:
        with Image.open(ruta) as img_pil:
            print(f"Se puede leer la imagen: {img_pil.format}, {img_pil.size}, {img_pil.mode}")
            return True
    except Exception as e:
        print("No se pudo leer: {e}")
        return False

verificar_ruta(ruta)
img_pil=Image.open(ruta)
img_np=np.array(img_pil)

gry=cv2.cvtColor(img_np,cv2.COLOR_BGR2GRAY) #Se pasa a Blanco y negro
gry2=cv2.GaussianBlur(gry,(0,0),1) #Se coloca el blur para quitar ondas
gry2=cv2.bilateralFilter(gry2,5,55,55) #Se filtra para reconocer letras
gry1=ImageEnhance.Sharpness(Image.fromarray(gry2)).enhance(3) #Se aumenta la nitidez de la imagen
#cv2.imwrite("gry1.png",gry2)
gry1.save("gry1.png") #Se guarda para verificar

th=cv2.adaptiveThreshold(np.array(gry1),255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,35,5) #Se coloca el umbral para eliminar ruido y aclarar la imagen
cv2.imwrite("th1.png",th) #Se guarda para verificar

kernel=np.ones((1,1),np.uint8)
th2=cv2.morphologyEx(th,cv2.MORPH_CLOSE,kernel,iterations=10) #Se usa para cerrar las letras
th2 = cv2.erode(th2, np.ones((1,1), np.uint8), iterations=1) #Aumentar el ancho del trazo
th2=cv2.copyMakeBorder(th2,10,10,10,10,cv2.BORDER_CONSTANT,value=255) #Aclarar los bordes de las letras
cv2.imwrite("th2.png",th2) #Se guarda para verificar

resized=cv2.resize(th2,None,fx=3,fy=3,interpolation=cv2.INTER_CUBIC) #Aumentar tamaño para mejor lectura
cv2.imwrite("resized.png",resized)#Se guarda para verificar

txt=pyt.image_to_string(resized,config="--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") #Se lee con pytesseract
#print(txt) #Se imprime para verificar

#Se llenan los campos y se da clic a Continuar

Cedula="Insertar cédula"
day="día de la fecha de expedición"
month="número del mes asociado al mes de la fecha de expedición"
year="año de la fecha de expedición"

form_data={
    "ContentPlaceHolder1_TextBox1":Cedula,
    "ContentPlaceHolder1_DropDownList1":day,
    "ContentPlaceHolder1_DropDownList2":month,
    "ContentPlaceHolder1_DropDownList3":year,
    "ContentPlaceHolder1_TextBox2":txt,
    "ContentPlaceHolder1_Button1": "Continuar"
}

response=requests.post(url,data=form_data)
print(response.status_code)

#Guardar PDF (lanza excepción si no es PDF)
pdf_path=save_pdf_from_response(response,OUT_PDF)
print("PDF guardado en:",pdf_path)

#Extraer texto del PDF
text=extract_text_from_pdf(pdf_path)

#Parsear campos
parsed=parse_fields_from_text(text)
# incluir metadatos
parsed["_meta"] = {
    "cedula_consulta": Cedula,
    "pdf_path": os.path.abspath(pdf_path)
}

#Guardar en JSON
json_path=save_json(parsed,OUT_JSON)
print("Datos guardados en JSON:",json_path)
print("Contenido extraído:",json.dumps(parsed, ensure_ascii=False, indent=2))




