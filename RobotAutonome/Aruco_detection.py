"""
il faut modifier la marge au dessus du rectangle des Aruco pour voir un peu plus au dessus
attention ca modifie la position de l'origine


il faut mettre une explication du repere Oxy
O est en haut à droite de l'image
x est horizontal vers la gauche
y est vertical vers le bas

et de l'ordre d'écriture des 4 points...
!!!!!!!!!!!!!!!!!!!
vidéo a refaire en mesurant précisement la postion de la caméra par rapport aux bords
aller plus vite dans les nouvements
bien travailler les alignements


"""

import time
import math
import cv2 # Import the OpenCV library
import numpy as np # Import Numpy library
import Variablesglobales
from ArucoDetection_definitions import *
import keyboard
import globals

DEBUG_MODE = False

# on defini la taille de la largeur et celle des marges autour, ce sont des hypothèses, le valeurs choisies fonctionnent
# pour avoir des portées globales
Variablesglobales.border_size=400  # 400 points entre le bord vertical et la balise inf de gauche
Variablesglobales.border_size_vert=300 # pour voir loin au dessus des balises sup, ca marche avec 300, ne change vrien avec 400
Variablesglobales.maxWidth=400 #400  largeur entre les balises BG et BD, idem on met ce qu'on veut
Variablesglobales.maxHeight = int((Variablesglobales.maxWidth*860)/1850) # = 266, 1860 et 860 sont les distancess réelles entre les 4 balises,
#on n'a pas du tout le choix ici
Variablesglobales.coef_red = 1850/400 # 4.625 coeficient pour passer des mm aux points, le denominateur vient du nombre de pixels entre les 2 balises du bas
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
    return bboxs, ids_sorted
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
# A RESPECTER !!!

#use location hold
marker_location_hold = True

#***************************************************************************
#fonction de compensation du fait que le code ARUCO du robot est placé au dessus
# le 0 est au coin haut gauche à 200,400 du point 1
# x est vers 2
# +y est vers 3
# fonction a reprendre
def camera_compensation(x_coordinate, y_coordinate):
    h_foam = 300 / Variablesglobales.coef_red  #350/2.31 hauteur cible fixée sur le robot
    # calcul position caméra
    # le rectangle des 4 balises fait 400 x (400*2.151=860 points)
    # il mesure réellement 860*1850 mm
    # coef_red = 860/400 # coeficient pour passer des mm aux points, DOUBLE DEFINITION !!!!!!
    h_camera = 1640 / Variablesglobales.coef_red # hauteur camera en point = 1640/2.31 =710
    # distance camera en X = 200 + 400/2 + 40/2.87 = 200 + 200 + 12 = 412 points
    # les coordonnées doivent etre exprimée dans le reperere de l'image modifiée

    x_camera = -1/Variablesglobales.coef_red  + Variablesglobales.maxWidth/2 + Variablesglobales.border_size  #-200
    y_camera = 200/Variablesglobales.coef_red + 570/Variablesglobales.coef_red + Variablesglobales.maxHeight + Variablesglobales.border_size_vert #400
    #x_camera = 596
    #y_camera = 528
    if DEBUG_MODE:
        print(f"xcam: {x_camera}")
        print(f"ycam: {y_camera}")

    x_cotangeante = (x_camera - x_coordinate)/h_camera
    y_cotangeante = (y_camera - y_coordinate)/h_camera

    x_correction = h_foam * x_cotangeante
    y_correction = h_foam * y_cotangeante

    x_compensated =  x_coordinate + x_correction
    y_compensated =  y_coordinate + y_correction
    return int(x_compensated), int(y_compensated)

def getAlpha(alpha, Xvect, Yvect):
    if Xvect > 0:
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
        if Yvect ==0:
            alpha = -1  # impossible, mais on evite la division par zéro
        elif Yvect > 0:
            alpha = 90
        elif Yvect < 0:
            alpha = 270

    elif Yvect == 0:
        if Xvect ==0:
            alpha = -1  # impossible, mais on evite la division par zéro
        elif Xvect > 0:
            alpha = 0
        elif Xvect < 0:
            alpha = 180

    return alpha
#***************************************************************************
def main():
    current_time1=time.time()
    # Load the ArUco dictionary
    if DEBUG_MODE:
        print(f"[INFO] detecting '{desired_aruco_dictionary1}' markers...")

    #dictionnaire pour 4 balises
    this_aruco_dictionary1 = cv2.aruco.getPredefinedDictionary(ARUCO_DICT[desired_aruco_dictionary1])
    this_aruco_parameters1 = cv2.aruco.DetectorParameters()
    # #dictionnaire pour robot, c'est le même on pourrait simplifier
    this_aruco_dictionary2 = cv2.aruco.getPredefinedDictionary(ARUCO_DICT[desired_aruco_dictionary1])
    this_aruco_parameters2 = cv2.aruco.DetectorParameters()

    # Start the video stream
    # video de la sequence de deplacement
    # la vidéo est trimée pour eliminer la zone de démarrage ou on ne voit pas les 4 ou 5 balises a prendre en compte pour le prochain film
    url = '/home/jomarin/robotAutonome/transformationPerspective/essai 09 04 24.mp4'
    #url = 'essai 09 04 24.mp4'

    cap = cv2.VideoCapture(url)
    # ou webcam du PC
    if not cap.isOpened():
        print("Cannot open camera")

    square_points=current_square_points
    while cap.isOpened():
        current_time=time.time()
        ret, frame = cap.read()
        if not ret:
            break

        # détection des balises ARUCO dans la vidéo d'origine.
        markers, ids = get_markers(frame, this_aruco_dictionary1, this_aruco_parameters1)

        #create copy of te initial 'clean frame'
        frame_clean=frame.copy()

        #get info over the different markers and display info
        left_corners, corner_ids = getMarkerCoordinates(markers, ids, 0)
        right_corners, corner_ids = getMarkerCoordinates(markers, ids, 1)
        # 1 right    2 ?

        # on met a jour les coordonnées, on garde les précedentes si une balise est cachée
        if marker_location_hold == True:
            if corner_ids is not None:
                count = 0
                for id in corner_ids:
                    if id in table_ids:
                        current_square_points[table_ids[id]-1] = left_corners[count]
                    count = count + 1
            left_corners = current_square_points
            corner_ids = [1, 2, 3, 4]

        # on affiche les contours et les points 0 et 1, toujours sur vidéo d'origine
        cv2.aruco.drawDetectedMarkers(frame, markers) #built in open cv function
        if start_time < current_time:
            draw_corners(frame, left_corners)
            draw_corners(frame, right_corners)
            draw_numbers(frame, left_corners, corner_ids)
            show_spec(frame,left_corners)

        frame_with_square, squareFound = draw_field(frame, left_corners, corner_ids)

        #les coordonnées ne sont pas toujours affichées dans le même ordre !!!!

        #recherche robot
        #extract square and show in extra window
        if start_time < current_time:
            if squareFound:
                square_points=left_corners

            # création d'un nouvelle image avec correction de perspective
            img_wrapped = four_point_transform(frame_clean, np.array(square_points)) # renvoi l'image redressée

            # recherche du robot, Detect 4x4 ArUco markers in the video frame
            h, w, _ = img_wrapped.shape
            marker_foam, ids_foam = get_markers(img_wrapped, this_aruco_dictionary2, this_aruco_parameters2)

            if ids_foam is not None and robot_id in ids_foam:
                left_corner_foam, corner_id_foam = getMarkerCoordinates(marker_foam, ids_foam, 0)
                centerCorner = getMarkerCenter_foam([marker_foam[ids_foam.index(robot_id)]])

                if DEBUG_MODE:
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
                xa = (marker_foam[ids_foam.index(robot_id)][0][0][0] + marker_foam[ids_foam.index(robot_id)][0][3][0])/2
                ya = (marker_foam[ids_foam.index(robot_id)][0][0][1] + marker_foam[ids_foam.index(robot_id)][0][3][1])/2
                xb = (marker_foam[ids_foam.index(robot_id)][0][1][0] + marker_foam[ids_foam.index(robot_id)][0][2][0])/2
                yb = (marker_foam[ids_foam.index(robot_id)][0][1][1] + marker_foam[ids_foam.index(robot_id)][0][2][1])/2
                if DEBUG_MODE:
                    print("xa=",xa)
                    print("ya=",ya)
                    print("xb=",xb)
                    print("yb=",yb)

                # on applique la compensation de la camera sur le vecteur
                xacor, yacor = camera_compensation(xa,ya)
                xbcor, ybcor = camera_compensation(xb,yb)
                if DEBUG_MODE:
                    print("xacor=",xacor)
                    print("yacor=",yacor)
                    print("xbcor=",xbcor)
                    print("ybcor=",ybcor)

                Xvect= xbcor-xacor
                Yvect= ybcor-yacor
                if DEBUG_MODE:
                    print("Xvect=",Xvect)
                    print("Yvect=",Yvect)

                # on calcule l'angle du vecteur de direction
                alpha = 0
                alpha = int(getAlpha(alpha, Xvect, Yvect))
                if DEBUG_MODE:
                    print("centercorner ",centerCorner)

            # update the markers positions when a markers is found. When no marker is found, use previous location
            if marker_location_hold == True:
                if corner_id_foam is not None:
                    #only one piece of foam
                    current_center_Corner[0] = centerCorner[0]
                centerCorner[0] = current_center_Corner[0]

            draw_corners(img_wrapped, centerCorner)

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

        # le repère est maintenant zero en ht a gauche, x vers le droite, y vers le bas.
        # coordonnées apparentes du robot
        # on ne peut pas faire un simple changement de repère, l'image a été construite à partir des 4 position des balises
        # il faut donc repartir de là, 200 de bordure, 400 entre X1 et X2, 400*2.151 entre Y1 et Y4
        # voici les coordonnées robot dans l'image, en point
        # il faut les coordonnées dans le repere 0XY
        x_coordinate = centerCorner[0][0]
        y_coordinate = centerCorner[0][1]

        #camera compensation
        x_coordinate_comp, y_coordinate_comp = camera_compensation(x_coordinate, y_coordinate)
        x_coordpixel = int(x_coordinate_comp)
        y_coordpixel = int(y_coordinate_comp)
        # il faut faire un changement de repère pour facilter la lecture
        # on place le zero sur la balise du haut à gauche  !!!!!

        x_coordmm = Variablesglobales.coef_red * (x_coordpixel - (Variablesglobales.border_size-750 / Variablesglobales.coef_red)) # 200*2.151
        y_coordmm = Variablesglobales.coef_red * (y_coordpixel - (Variablesglobales.border_size_vert-455 / Variablesglobales.coef_red)) #400*2.151

        # dessine une croix verte sur le code ARUCO du robot, coordonnées corrigées
        img_wrapped = cv2.line(img_wrapped, (x_coordinate_comp, 0), (x_coordinate_comp, h), (0, 255, 0), 2)
        img_wrapped = cv2.line(img_wrapped, (0, y_coordinate_comp), (w, y_coordinate_comp), (0, 255, 0), 2)

        # pour voir le vecteur orientation il faut le dessiner apres la croix verte
        img_wrapped = cv2.line(img_wrapped, (xacor, yacor),(xbcor, ybcor),(255, 0, 0), 2)
        img_wrapped = cv2.line(img_wrapped, (100, 100), (100 + Xvect, 100 + Yvect), (255, 0, 255), 2)


        # affiche les axes
        # en X on a mis 400 pts à cgauche, c'est à dire 1500mm, alors que le bord de la piste n'est qu'a 700mm soit 187 points
        # il y a 50 mm qui se balladent
        # en Y on a mis 300 pts au dessus, c'est à dire 1125mm, alors que le bord de la piste n'est qu'a 500mm soit 153 points
        # il y a 100 mm qui se balladent
        img_wrapped=cv2.line(img_wrapped,(187,200), (187,333), (255,0,0), 2) #Y
        img_wrapped=cv2.line(img_wrapped,(187,200), (400,200), (255,0,0), 2) #X
        #donc 187,153 est le décalage en point pour etre positionné dans le repere centré dans l'angle haut et gauche
        #donc 701,574 en mm
        Xrobot = centerCorner[0][0]-187
        Yrobot = centerCorner[0][1]-153

        if DEBUG_MODE:
            print("Xrobot ",centerCorner[0][0]-187)
            print("Yrobot ",centerCorner[0][1]-153)
        # affiche les coordonnées sur l'image
        cv2.putText(img_wrapped, format(int(x_coordmm)), (10,40),cv2.FONT_HERSHEY_SIMPLEX, 1,(0, 255, 0), 2)
        cv2.putText(img_wrapped, format(int(y_coordmm)), (130,40),cv2.FONT_HERSHEY_SIMPLEX, 1,(0, 255, 0), 2)
        cv2.putText(img_wrapped, format(alpha), (10,70),cv2.FONT_HERSHEY_SIMPLEX, 1,(0, 255, 255), 2)
        # affiche le nom des axes
        cv2.putText(img_wrapped, 'X', (410,153),cv2.FONT_HERSHEY_SIMPLEX, 1,(255, 0,0), 2)
        cv2.putText(img_wrapped, 'Y', (153,380),cv2.FONT_HERSHEY_SIMPLEX, 1,(255, 0,0), 2)
        cv2.putText(img_wrapped, '0', (190,180),cv2.FONT_HERSHEY_SIMPLEX, 1,(255, 0,0), 2)

        globals.x_position = Xrobot
        globals.x_position = Yrobot
        globals.y_position = alpha

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


