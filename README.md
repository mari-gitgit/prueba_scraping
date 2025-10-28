# prueba_scraping

Para comenzar se deben instalar las librerias:
- os
- urllib.parse
- requests
- bs4
- pytesseract
- cv2
- time
- PIL
- numpy
- scipy.ndimage
- pdfplumber

Una vez instaladas las librerías, debemos dirigirnos a la línea 142 o la que tenga el siguiente texto:

`ruta=os.path.join(r"nombre_ruta",nombre_img) #Cambiar por nombre de la carpeta o ruta correcta`

Y cambiar el nombre de la ruta por el del dispositivo que se está usando.

Finalmente, en los campos de las líneas de la 208 a la 211 se agregan los datos:

`Cedula="Insertar cédula"
day="día de la fecha de expedición"
month="número del mes asociado al mes de la fecha de expedición"
year="año de la fecha de expedición"`

EL código comenzará definiendo algunas funciones para el procesado y el guardado del PDF. Luego procesará el Captcha y llenará el formulario de acuerdo a los valores anteriormente definidos. Finalmente, mostrará un JSON con los datos solicitados.
