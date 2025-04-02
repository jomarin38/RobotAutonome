"""
sortir egalement l'orientation du robot


il faut modifier la marge au dessus du rectangle des Aruco pour voir un peu plus au dessus
attention ca modifiera la position de l'origine


il faut mettre une explication du repere Oxy
O est en haute à droite de l'image
x est horizontal vers la gauche
y est vertical vers le bas

et de l'ordre d'écriture des 4 points...
!!!!!!!!!!!!!!!!!!!
vidéo a refaire en mesurant précisement la postion de la caméra par rapport aux bords
aller plus vite dans les nouvements
bien travailler les alignements


"""

#!/usr/bin/env python
# %%
import time
import math
import cv2 # Import the OpenCV library
import numpy as np # Import Numpy library
import Variablesglobales
from ArucoDetection_definitions import *
import keyboard
import globals

# on defini la taille de la largeur et celle des marges autour
# pour avoir des portées globales
Variablesglobales.border_size=400  
Variablesglobales.border_size_vert=500 # pour voir loin au dessus des balises sup, ca marche avec 300, ne change vrien avec 400
Variablesglobales.maxWidth=400 #300 ca donne une image etriquée
Variablesglobales.maxHeight = int((Variablesglobales.maxWidth*860)/1850) # = 186, 1850 et 860 sont les distancess réelles entre les 4 balises
Variablesglobales.coef_red = 1850/800 # = 2.31 coeficient pour passer des mm aux points, le denominateur vient du nombre de pixels entre les 2 balises du bas
# pour mesurer il faut faire une copie d'écran de la vidéo en pause, et mesurer avec paint dans l'image obtenue
# le resultat serait différent si on prenait les balises du haut...

start_time = time.time()
# dico pour ARUCO table
desired_aruco_dictionary1 = "DICT_4X4_50"
start_time = time.time()
# dico pour ARUCO robot, il peut etre différent
desired_aruco_dictionary2 = "DICT_4X4_50"

# The different ArUco dictionaries built into the OpenCV library. 
ARUCO_DICT = {
  "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
  "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
  "DICT_4X4_250": cv2.aruco.DICT_4X4_250,
  "DICT_4X4_1000": cv2.aruco.DICT_4X4_1000,
  "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
  "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
  "DICT_5X5_250": cv2.aruco.DICT_5X5_250,
  "DICT_5X5_1000": cv2.aruco.DICT_5X5_1000,
  "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
  "DICT_6X6_100": cv2.aruco.DICT_6X6_100,
  "DICT_6X6_250": cv2.aruco.DICT_6X6_250,
  "DICT_6X6_1000": cv2.aruco.DICT_6X6_1000,
  "DICT_7X7_50": cv2.aruco.DICT_7X7_50,
  "DICT_7X7_100": cv2.aruco.DICT_7X7_100,
  "DICT_7X7_250": cv2.aruco.DICT_7X7_250,
  "DICT_7X7_1000": cv2.aruco.DICT_7X7_1000,
  "DICT_ARUCO_ORIGINAL": cv2.aruco.DICT_ARUCO_ORIGINAL
}
#***************************************************************************
def get_markers(vid_frame, aruco_dictionary, aruco_parameters):
    detector = cv2.aruco.ArucoDetector(aruco_dictionary, aruco_parameters)
    bboxs, ids, rejected = detector.detectMarkers(vid_frame)
    if ids is not None:
        ids_sorted=[]
        for id_number in ids:
            ids_sorted.append(id_number[0])
    else:
        ids_sorted=ids
    return bboxs,ids_sorted
#***************************************************************************
# ces valeurs ne sont pas utilisées !
init_loc_1=[10,400]
init_loc_2=[400,400]
init_loc_3=[400,10]
init_loc_4=[10,10]
#initiaize locations
current_square_points=[init_loc_1,init_loc_2,init_loc_3,init_loc_4]
current_center_Corner=[[0,0]]
# ID du robot
robot_id = 10

#Map associating ids with corners
# bas gauche, haut gauche, haut droit, bas droit
table_ids = {21:1, 23:2, 22:3, 20:4}

#use location hold
marker_location_hold = True

#***************************************************************************
#fonction de compensation du fait que le code ARUCO du robot est placé au dessus
# le 0 est au coin haut gauche à 200,400 du point 1
# x est vers 2 
# +y est vers 3
# fonction a reprendre
def camera_compensation(x_coordinate, y_coordinate):

  
    h_foam = 151.5  #350/2.31 hauteur cible fixée sur le robot
    # calcul position caméra
    # le rectangle des 4 balises fait 400 x (400*2.151=860 points)
    # il mesure réellement 860*1850 mm
    # coef_red = 860/400 # coeficient pour passer des mm aux points, DOUBLE DEFINITION !!!!!!
    h_camera = 1640 / Variablesglobales.coef_red # hauteur camera en point = 1640/2.31 =710
    # distance camera en X = 200 + 400/2 + 40/2.87 = 200 + 200 + 12 = 412 points
    x_camera = -40/Variablesglobales.coef_red  + Variablesglobales.maxWidth/2 + Variablesglobales.border_size  #-200
    y_camera = 200/Variablesglobales.coef_red + Variablesglobales.maxHeight + Variablesglobales.border_size_vert #400
    # distance camera en Y = 430mm soit 430/2.151 = 200 + 860 + 400 = 1460
    # distance X point/camera = 412 - x_coordinate
    # distance Y point/camera = 1460 - y_coordinate
    # cotangX = distance X point_camera/h_camera
    # cotangY = distance Y point_camera/h_camera
    # correction X = 300 * cotangx
    # correction Y = 300 * cotangy
    x_cotangeante = (x_camera - x_coordinate)/h_camera
    y_cotangeante = (y_camera - y_coordinate)/h_camera
    x_correction= h_foam * x_cotangeante
    y_correction= h_foam * y_cotangeante
    #print("cotangx ",x_cotangeante,"cotangy ",y_cotangeante)
    #print("x_correction ",x_correction,"y_correction ",y_correction)
    x_compensated =  x_coordinate + x_correction
    y_compensated =  y_coordinate + y_correction



    return int(x_compensated), int(y_compensated)
#***************************************************************************
def update_position():
    current_time1=time.time()
    # Load the ArUco dictionary
    print("[INFO] detecting '{}' markers...".format(desired_aruco_dictionary1))
    this_aruco_dictionary1 = cv2.aruco.getPredefinedDictionary(ARUCO_DICT[desired_aruco_dictionary1])
    this_aruco_parameters1 = cv2.aruco.DetectorParameters()
    this_aruco_dictionary2 = cv2.aruco.getPredefinedDictionary(ARUCO_DICT[desired_aruco_dictionary1])
    this_aruco_parameters2 = cv2.aruco.DetectorParameters()
    
    # Start the video stream
    # video de la sequence de deplacement
    # la vidéo est trimée pour eliminer la zone de démarrage ou on ne voit pas les 4 ou 5 balises
    # a prendre en compte pour la prochaine
    #film
    #url = 'Video 24 avril - Trim.mp4'
    #cap = cv2.VideoCapture(url)
    # ou webcam du PC
    cap = cv2.VideoCapture(1)
    cap = cv2.VideoCapture('/dev/video2')
    if not cap.isOpened():
        print("Cannot open camera")
    # pour forcer les dimensions de l'image.
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,1080)
    square_points=current_square_points
    while True:
        current_time=time.time()
        print("time :",round((time.time()-current_time1),1))
        ret, frame = cap.read()
        # Detect 4x4 ArUco markers in the video frame
        markers,ids=get_markers(frame, this_aruco_dictionary1, this_aruco_parameters1)

        #create copy of te initial 'clean frame'
        frame_clean=frame.copy()

        #get info over the different markers and display info
        left_corners,corner_ids=getMarkerCoordinates(markers,ids,0)
        right_corners,corner_ids=getMarkerCoordinates(markers,ids,1) 
        # 1 right    2 ?


        #update the markers positions when a markers is found. When no marker is found, use previous location
        if marker_location_hold==True:
            if corner_ids is not None:
                count=0
                for id in corner_ids:
                    if id in table_ids:
                        current_square_points[table_ids[id]-1]=left_corners[count]
                    count=count+1
            left_corners=current_square_points
            corner_ids=[1,2,3,4]

        
        
        cv2.aruco.drawDetectedMarkers(frame, markers) #built in open cv function
        if start_time < current_time:    
            draw_corners(frame,left_corners)
            draw_corners(frame,right_corners)
            draw_numbers(frame,left_corners,corner_ids)
            #draw_numbers(frame,right_corners,corner_ids)
            show_spec(frame,left_corners)
   
        frame_with_square,squareFound=draw_field(frame,left_corners,corner_ids)
        #frame_with_square,squareFound=draw_field(frame,right_corners,corner_ids)
        #print("coord coin 0",left_corners)
        #print("ids",corner_ids)
        #print("coord coin 1",right_corners)
        
        #les coordonnées ne sont pas affichées dans le même ordre !!!!
            
        #recherche robot   
        #extract square and show in extra window
        if start_time < current_time:
            if squareFound:
                square_points=left_corners

            # correction de perspective
            img_wrapped=four_point_transform(frame_clean, np.array(square_points))
            # renvoi image redressée
            
            # recherche du robot, Detect 4x4 ArUco markers in the video frame
            h, w, c = img_wrapped.shape
            marker_foam,ids_foam=get_markers(img_wrapped, this_aruco_dictionary2, this_aruco_parameters2)
            if ids_foam is not None and robot_id in ids_foam:
                left_corner_foam,corner_id_foam=getMarkerCoordinates(marker_foam,ids_foam,0)
                centerCorner=getMarkerCenter_foam([marker_foam[ids_foam.index(robot_id)]])
                #print("corner ID ",corner_id_foam)
                print("coins aruco robot ",marker_foam[ids_foam.index(robot_id)])
                print("x1=",marker_foam[ids_foam.index(robot_id)][0][0][0])
                print("y1=",marker_foam[ids_foam.index(robot_id)][0][0][1])
                print("x2=",marker_foam[ids_foam.index(robot_id)][0][1][0])
                print("y2=",marker_foam[ids_foam.index(robot_id)][0][1][1])
                print("x3=",marker_foam[ids_foam.index(robot_id)][0][2][0])
                print("y3=",marker_foam[ids_foam.index(robot_id)][0][2][1])
                print("x4=",marker_foam[ids_foam.index(robot_id)][0][3][0])
                print("y4=",marker_foam[ids_foam.index(robot_id)][0][3][1])
                # calcul vecteur direction 
                xa= (marker_foam[ids_foam.index(robot_id)][0][0][0] + marker_foam[ids_foam.index(robot_id)][0][3][0])/2
                ya= (marker_foam[ids_foam.index(robot_id)][0][0][1] + marker_foam[ids_foam.index(robot_id)][0][3][1])/2
                xb= (marker_foam[ids_foam.index(robot_id)][0][1][0] + marker_foam[ids_foam.index(robot_id)][0][2][0])/2
                yb= (marker_foam[ids_foam.index(robot_id)][0][1][1] + marker_foam[ids_foam.index(robot_id)][0][2][1])/2
                print("xa=",xa)
                print("ya=",ya)
                print("xb=",xb)
                print("yb=",yb)
                xacor, yacor=camera_compensation(xa,ya)
                xbcor, ybcor=camera_compensation(xb,yb)
                print("xacor=",xacor)
                print("yacor=",yacor)
                print("xbcor=",xbcor)
                print("ybcor=",ybcor)
                Xvect= xbcor-xacor
                Yvect= ybcor-yacor
                print("Xvect=",Xvect)
                print("Yvect=",Yvect)
                alpha = 0
                if Xvect > 0 :
                    if Yvect > 0:
                        alpha = (math.atan2(Yvect,Xvect) * 180/math.pi)
                    elif Yvect < 0:
                        alpha = 270 +  (math.atan2(Xvect,-Yvect) * 180/math.pi)
             
                elif Xvect < 0:
                    if Yvect > 0:
                        alpha = 90 + (math.atan2(-Xvect,Yvect) * 180/math.pi)
                    elif Yvect < 0:
                        alpha = 180 +  (math.atan2(-Yvect,-Xvect) * 180/math.pi)       
                
                elif Xvect == 0:
                    if Yvect ==0 :
                        alpha = -1  # impossible, mais on evite la division par zéro
                    elif Yvect > 0 :
                        alpha = 90 
                    elif Yvect < 0 :
                        alpha = 270 
                elif Yvect == 0:
                    if Xvect ==0 :
                        alpha = -1  # impossible, mais on evite la division par zéro
                    elif Xvect > 0 :
                        alpha = 0
                    elif Xvect < 0 :
                        alpha = 180 

                alpha1 = int(alpha)
                print("alpha=",alpha1)
                
                # on a les coordonnées des 4 points du robot
                # mais les 4 sortent d'un coup !
                # faut il leur faire subir une correction pour déterminer l'angle ?
                # oui  rvec, tvec,_ = cv2.aruco.estimatePoseSingleMarkers(marker_foam[ids_foam.index(robot_id)], 0.1, mtx, dist) 
                # calcul angle
                #print("left_corner ",left_corner_foam)
                print("centercorner ",centerCorner)
           
            #update the markers positions when a markers is found. When no marker is found, use previous location
            if marker_location_hold==True:
                if corner_id_foam is not None:
                    #only one piece of foam
                    current_center_Corner[0]=centerCorner[0]
                centerCorner[0]=current_center_Corner[0]              
            draw_corners(img_wrapped,centerCorner)
            #dessine une croix rouge sur le code ARUCO du robot
            img_wrapped=cv2.line(img_wrapped,(centerCorner[0][0],0), (centerCorner[0][0],h), (0,0,255), 2)
            img_wrapped=cv2.line(img_wrapped,(0,(centerCorner[0][1])), (w,(centerCorner[0][1])), (0,0,255), 2)
            #on dessine le vecteur
            
            # bleu pour a
            img_wrapped=cv2.line(img_wrapped,(0,0),(xacor,yacor),(255,0,0),2)
            # magenta pour b
            img_wrapped=cv2.line(img_wrapped,(0,0),(xbcor,ybcor),(255,0,255),2)
            draw_numbers(img_wrapped,left_corner_foam,corner_id_foam)
            cv2.imshow('img_wrapped',img_wrapped)
            #affiche image deformée

        # Display the resulting frame
        cv2.imshow('frame_with_square',frame_with_square)
        #affiche image avec rectangle et position ARUCO
        #cv2.imshow('img_cropped',img_cropped)

        # compensation d'altitude ARUCO du Robot
        #print("centerCorner ",centerCorner)
        # le repère est maintenant zero en ht a gauche, x vers le droite, y vers le bas.
        # coordonnées apparentes du robot
        # on ne peut pas faire un simple changement de repère, l'image a été construite à partir des 4 position des balises
        # il faut donc repartir de là, 200 de bordure, 400 entre X1 et X2, 400*2.151 entre Y1 et Y4
        # 
        x_coordinate=centerCorner[0][0]
        y_coordinate=centerCorner[0][1]
        #print("Optical position: ",x_coordinate,", ",y_coordinate)
        #print("format image init H L ",frame_with_square.shape)  #1920*1080
        #print("format image deformée H L ",img_wrapped.shape)   #1460*800
        #dessine une croix bleue sur le code ARUCO du robot, coordonnées apparentes
        #img_wrapped=cv2.line(img_wrapped,(x_coordinate,0), (x_coordinate,h), (255,0,0), 2)
        #img_wrapped=cv2.line(img_wrapped,(0,y_coordinate), (w,y_coordinate), (255,0,0), 2)
        
        #camera compensation
        x_coordinate_comp,y_coordinate_comp=camera_compensation(x_coordinate,y_coordinate)
        #print("Position after compensation: ",x_coordinate_comp,", ",y_coordinate_comp)
        x_coordmm = int(x_coordinate_comp * 2.151)
        y_coordmm = int(y_coordinate_comp * 2.151)
        # il faut faire un changement de repère pour facilter la lecture
        # on place le zero sur la balise du haut à gauche
        x_coordmm = x_coordmm -430 # 200*2.151
        y_coordmm = y_coordmm -860 #400*2.151
        #print("Position robot en mm: ",x_coordmm,", ",y_coordmm)
        #print("- ")
        globals.x_positon = x_coordmm
        globals.y_positon = y_coordmm

        #dessine une croix verte sur le code ARUCO du robot, coordonnées corrigées
        img_wrapped=cv2.line(img_wrapped,(x_coordinate_comp,0), (x_coordinate_comp,h), (0,255,0), 2)
        img_wrapped=cv2.line(img_wrapped,(0,y_coordinate_comp), (w,y_coordinate_comp), (0,255,0), 2)
        
        #pour voir le vecteur orientation il faut le dessiner apres la croix verte
        img_wrapped=cv2.line(img_wrapped,(xacor,yacor),(xbcor,ybcor),(255,0,0),2)
        img_wrapped=cv2.line(img_wrapped,(100,100),(100+Xvect,100+Yvect),(255,0,255),2)
        # affiche les coordonnées sur l'image
        cv2.putText(img_wrapped, format(x_coordmm), (10,40),cv2.FONT_HERSHEY_SIMPLEX, 1,(0, 255, 0), 2)
        cv2.putText(img_wrapped, format(y_coordmm), (130,40),cv2.FONT_HERSHEY_SIMPLEX, 1,(0, 255, 0), 2)
        cv2.putText(img_wrapped, format(alpha1), (10,70),cv2.FONT_HERSHEY_SIMPLEX, 1,(0, 255, 255), 2)

        # affiche les axes
        img_wrapped=cv2.line(img_wrapped,(200,400), (200,600), (255,0,0), 2)
        img_wrapped=cv2.line(img_wrapped,(200,400), (400,400), (255,0,0), 2) 
        # affiche le nom des axes
        cv2.putText(img_wrapped, 'X', (410,410),cv2.FONT_HERSHEY_SIMPLEX, 1,(255, 0,0), 2)
        cv2.putText(img_wrapped, 'Y', (190,620),cv2.FONT_HERSHEY_SIMPLEX, 1,(255, 0,0), 2)        
        cv2.putText(img_wrapped, '0', (190,390),cv2.FONT_HERSHEY_SIMPLEX, 1,(255, 0,0), 2)       
        
        
        
        cv2.imshow('img_wrapped',img_wrapped)
        
        #"""
        if cv2.waitKey(1) == ord('q'):
            break
            
    # Close down the video stream
    cap.release()
    cv2.destroyAllWindows()
    return centerCorner 
#***************************************************************************   

if __name__ == '__main__':
    foam_center=main()  #pull foam location from markers
    
# %%
# %%
