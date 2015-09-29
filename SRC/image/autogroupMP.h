// -*- C++ -*-
// $RCSfile: autogroupMP.h,v $
// $Revision: 1.2 $
// $Author: langer $
// $Date: 2011/07/14 21:19:33 $

/* This software was produced by NIST, an agency of the U.S. government,
 * and by statute is not subject to copyright in the United States.
 * Recipients of this software assume all responsibilities associated
 * with its operation, modification and maintenance. However, to
 * facilitate maintenance we ask that before distributing modified
 * versions of this software, you first contact the authors at
 * oof_manager@nist.gov. 
 */

#include <oofconfig.h>

#ifndef AUTOGROUPMP_H
#define AUTOGROUPMP_H

class CMicrostructure;
class OOFImage;

#include <string>

const std::string *autogroup(
	     CMicrostructure*, OOFImage*, const std::string&);


#endif // autogroupmp_h
