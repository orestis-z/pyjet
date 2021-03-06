# from https://github.com/dm6718/Massive-Spring-Pendulum/blob/master/Massive%20Spring%20Pendulum.py
import jet 
import numpy
from jet.jit import jit
from scipy.integrate import odeint
from utils import profile


#Create spring dictionary
spring = {
    'm'     :   1.0,      # Mass of spring in kg
    'k'     :   1.0e3,  # Spring constant Nm^-1
    'l'     :   3.0e-2  # Rest length in m
    }

#Specify mass of attachment
mass = 1.0  # Mass of attachment in kg

#Return derivatives of the array z (= [theta, theta_dot, x, x_dot])
@jit
def deriv(z, t):
    m = spring['m']
    k = spring['k']
    l = spring['l']
    M = mass
    g = 9.8
    
    return jet.array([
        z[1],
        -1.0/(l+z[2])*(2*z[1]*z[3]+g*(m/2+M)/(m/3+M)*jet.sin(z[0])),
        z[3],
        (l+z[2])*z[1]**2+(m/2+M)/(m/3+M)*g*jet.cos(z[0])-1.0/(m/3+M)*k*z[2]
        ])

#Create time steps
time = numpy.linspace(0.0, 10.0, 1e7)

#Specify initial conditions
init = numpy.array([jet.pi  / 2, 0, mass * 9.8 / spring['k'], 0]) # initial values
            #array([theta, theta_dot, x, x_dot])

profile_derive = lambda: profile(lambda: deriv(init, time[0]))
profile_odeint = lambda: profile(lambda: odeint(deriv, init, time))

print('jet_mode = True')
print('derivatives: %f, %f' % (profile_derive(), profile_derive()))
print('integration: %f' % profile_odeint())

jet.set_options(jet_mode=False)

print('---')
print('jet_mode = False')
print('derivatives: %f' % profile_derive())
print('integration: %f' % profile_odeint())
