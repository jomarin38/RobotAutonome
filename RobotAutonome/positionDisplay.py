import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.pyplot import imread
import globals
from math import cos, sin

debug = True

def create_arrow():
    return plt.arrow(globals.x_position,
                      globals.y_position,
                      arrow_length * cos(globals.direction),
                      arrow_length * sin(globals.direction),
                      width=20,
                      color='red')


def init():
    return create_arrow(),

def animate(i):
    if debug and (i % 20) ==0:
        print(globals.x_position, globals.y_position)
    return create_arrow(),


img = imread("Capture table2.JPG")

fig = plt.figure()
fig.set_dpi(100)
fig.set_size_inches(7, 6.5)
increment = 0

arrow_length = 50
ax = plt.axes(xlim=(0, 3000), ylim=(0, 2000))
patch = plt.Circle((50, 50), 50, fc='r')
#patch = plt.arrow(globals.x_position,
#                  globals.y_position,
#                  arrow_length * cos(globals.direction),
#                  arrow_length * sin(globals.direction),
#                  witdh=2)

def display_position():

    anim = animation.FuncAnimation(fig, animate,
                                   init_func=init,
                                   frames=360,
                                   interval=20,
                                   blit=True)

    plt.imshow(img,zorder=0,  extent=[0.1, 3000.0, 0.1, 2000.0])
    #anim.save('the_movie.mp4', writer = 'ffmpeg', fps=30)
    plt.show()

