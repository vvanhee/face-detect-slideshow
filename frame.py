import glob
import os
import shutil
#import subprocess
from PIL import Image
from PIL import ImageDraw
from googleapiclient import discovery
from oauth2client.client import GoogleCredentials
import base64
import piexif
import time


path = 'C:\\Users\\vvanh\\Pictures'
croppath = path + "\\tmp"
frameWidth=480
frameHeight=264
maxWidthForSending = 2000

def autoRotateAndResize(fullfilename,cropWidth,save=False):
    """ This function autorotates a picture and resizes it"""
    maxsize = (cropWidth,20000)
    name=os.path.basename(fullfilename)
    cropfname=croppath+"\\"+name
    image = Image.open(fullfilename)
    try:
        exif = image._getexif()
        #exifDict = piexif.load(image.info["exif"])
    except:
        print("Could not get exif - Bad image!")
        return False
    if exif == None:
        print("Could not get exif - Bad image!")
        return False
    (width, height) = image.size
    # print "\n===Width x Heigh: %s x %s" % (width, height)
    orientation_key = 274 # cf ExifTags
    #exifbytes = piexif.dump(exif)
    if orientation_key in exif:
        orientation = exif[orientation_key]
        rotate_values = {
            3: 180,
            6: 270,
            8: 90
        }
        if orientation in rotate_values:
            # Rotate and save the picture
            image = image.rotate(rotate_values[orientation],expand=True)
            image.thumbnail(maxsize)
            if save == True:
                #image.save(cropfname, quality=75,exif=exifbytes)
                image.save(cropfname, quality=75)
            return image

    image.thumbnail(maxsize)
    if save == True:
        image.save(cropfname, quality=75)
    return image

def get_vision_service():
    #credentials = GoogleCredentials.get_application_default()
    credentials = GoogleCredentials.from_stream('Digital Frame-d4547eb38205.json')
    return discovery.build('vision', 'v1', credentials=credentials)

def detect_face(face_file, max_results=3):
    """Uses the Vision API to detect faces in the given file.

    Args:
        face_file: A file-like object containing an image with faces.

    Returns:
        An array of dicts with information about the faces in the picture.
    """
    image_content = face_file.read()
    batch_request = [{
        'image': {
            'content': base64.b64encode(image_content).decode('utf-8')
            },
        'features': [{
            'type': 'FACE_DETECTION',
            'maxResults': max_results,
            }]
        }]

    service = get_vision_service()
    request = service.images().annotate(body={
        'requests': batch_request,
        })
    response = request.execute()
    if response['responses'] and 'faceAnnotations' in response['responses'][0]:
        return response['responses'][0]['faceAnnotations']
    else:
        return -1

def highlight_faces(image, faces, output_filename):
    """Draws a polygon around the faces, then saves to output_filename.

    Args:
      image: a file containing the image with the faces.
      faces: a list of faces found in the file. This should be in the format
          returned by the Vision API.
      output_filename: the name of the image file to be created, where the
          faces have polygons drawn around them.
    """
    im = Image.open(image)
    draw = ImageDraw.Draw(im)

    for face in faces:
        box = [(v.get('x', 0.0), v.get('y', 0.0))
               for v in face['fdBoundingPoly']['vertices']]
        draw.line(box + [box[0]], width=5, fill='#00ff00')
    im.save(output_filename)

def avgYForFaces(faces):
    faceYCenters=[]
    for face in faces:
        (top_y,bottom_y) = getTopAndBottom(face)
        faceYCenters.append((bottom_y+top_y)/2)
    return sum(faceYCenters)/len(faceYCenters)

def maxYDifference(faces):
    topsAndBottoms = []
    for face in faces:
        (top_y,bottom_y) = getTopAndBottom(face)
        topsAndBottoms.append(top_y)
        topsAndBottoms.append(bottom_y)        
    return max(topsAndBottoms)-min(topsAndBottoms)    

def getTopAndBottom(face):
    try:
        top_y = face['fdBoundingPoly']['vertices'][0]['y']
    except:
        top_y = 0
    try:
        bottom_y = face['fdBoundingPoly']['vertices'][2]['y']
    except:
        bottom_y = frameHeight
    return (top_y,bottom_y)

def cropToFace(fullfilename, resized_width, face):
    (top_y,bottom_y) = getTopAndBottom(face)
    midface_y_sent = (top_y+bottom_y)/2
    cropToY(fullfilename, resized_width, midface_y_sent)
    
def cropToY(fullfilename, resized_width, yCtr):
    scaledImg = autoRotateAndResize(fullfilename,frameWidth)
    (scaled_w,scaled_h)=scaledImg.size
    resized_height = scaled_h*resized_width/scaled_w
    y_scaled=yCtr*frameWidth/resized_width
    print("scaled h: " + str(scaled_h) + " scaled w: " + str(scaled_w) + " y_scaled = " + str(y_scaled))
    if y_scaled < 0.5*frameHeight:
        print("faces high")
        scaledImg=scaledImg.crop((0,0,frameWidth,frameHeight))
    elif y_scaled > scaled_h-0.5*frameHeight:
        print("faces low")
        scaledImg=scaledImg.crop((0,scaled_h-frameHeight,frameWidth,scaled_h))
    else:
        scaledImg=scaledImg.crop((0,y_scaled-frameHeight/2,frameWidth,y_scaled+frameHeight/2))
    name=os.path.basename(fullfilename)
    cropfname=croppath+"\\"+name
    os.remove(cropfname)
    try:
        scaledImg.save(cropfname, quality=85)
    except:
        return
    os.remove(fullfilename)
    
#########################

if os.path.isdir(croppath):
    shutil.rmtree(croppath)
os.mkdir(croppath)

for fname in glob.glob(path+"\\*.png"):
    name=os.path.basename(fname)
    os.system('convert ' + fname + ' ' + path + '\\' + name + ".jpg")

for fname in glob.glob(path+"\\*.jpg"):
    name=os.path.basename(fname)
    img = autoRotateAndResize(fname, maxWidthForSending,save=True)
    if img != False:
        print("Detecting faces in " + name + "...")
        cropfname=croppath+"\\"+name
        with open(cropfname,'rb') as image:
            faces = detect_face(image)
            #print(faces)
            image.seek(0)
            #highlight_faces(image, faces, path+"\\tmp.jpg")
            image.close()
            (resized_w,resized_h) = img.size
            if faces == -1: # no faces detected
                print("No faces detected in this photo.")
                cropToY(fname, resized_w, resized_h/2) # crop to center Y
            elif len(faces) > 1:
                print('Found {} faces'.format(len(faces)))           
                maxYDiff=maxYDifference(faces)
                scaledYDiff=maxYDiff*frameWidth/resized_w
                if scaledYDiff>frameHeight*1.1: # then crop to first face
                    cropToFace(fname, resized_w, faces[0])
                else: #take the average Y for centers of faces
                    yCenter=avgYForFaces(faces)
                    cropToY(fname, resized_w, yCenter)
            else: # one face detected
                print("Found one face")
                cropToFace(fname, resized_w, faces[0])

timestr = time.strftime("%Y-%m-%d-%H-%M-%S")
shutil.move(croppath,path+"/crops-"+timestr)

