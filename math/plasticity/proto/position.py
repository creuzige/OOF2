# -*- python -*-

# This software was produced by NIST, an agency of the U.S. government,
# and by statute is not subject to copyright in the United States.
# Recipients of this software assume all responsibilities associated
# with its operation, modification and maintenance. However, to
# facilitate maintenance we ask that before distributing modified
# versions of this software, you first contact the authors at
# oof_manager@ctcms.nist.gov. 



# Encapsulated position class, with fun emulation.

import types

class Oops:
    def __init__(self, msg):
        self.msg = msg
    def __repr__(self):
        return "Oops: %s" % self.msg


    
class Position:
    def __init__(self,x=0,y=0,z=0):
        self.x = x
        self.y = y
        self.z = z

    def clone(self):
        return Position(x=self.x, y=self.y, z=self.z)
    
    def __iadd__(self, other):
        self.x += other.x
        self.y += other.y
        self.z += other.z
        return self
    
    def __add__(self,other):
        res = Position(self.x,self.y,self.z)
        res += other
        return res

    def __neg__(self):
        return Position(-self.x,-self.y,-self.z)

    def __isub__(self,other):
        self.x -= other.x
        self.y -= other.y
        self.z -= other.z
        return self
    def __sub__(self,other):
        res = Position(self.x, self.y)
        res -= other
        return res
    
    def __imul__(self,other):
        if type(other)==types.FloatType or type(other)==types.IntType:
            self.x *= other
            self.y *= other
            self.z *= other
            return self
        raise Oops("Type: Can't imul by %s." % type(other))

    def __mul__(self,other):
        if type(other)==types.FloatType or type(other)==types.IntType:
            res = Position(self.x*other,self.y*other)
        else:
            if isinstance(other,Position):
                res = self.x*other.x+self.y*other.y
            else:
                raise Oops("Type: Wanted %s or %s, got %s." %
                           (Position, types.IntegerType, type(other)) )
        return res

    def __rmul__(self,other):
        return self.__mul__(other)

    # Cross product.
    # def __mod__(self,other):
    #     return self.x*other.y-self.y*other.x

    # def __rmod__(self,other):
    #     return other.__mod__(self)
    

    def __pow__(self, other):
        if other==2:
            return self.x*self.x+self.y*self.y+self.z*self.z
        raise Oops("Type: Wanted %s, got %s." %
                   (types.IntegerType,type(other)) )

    def __repr__(self):
        return "Position(%g,%g,%g)" % (self.x, self.y,self.z)

    def __getitem__(self,idx):
        if idx==1:
            return self.x
        else:
            if idx==2:
                return self.y
            else:
                if idx==3:
                    return self.z
        raise Oops("Range: %s is not 1, 2, or 3." % idx)
    
        
