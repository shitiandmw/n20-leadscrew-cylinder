#include "protection_logic.h"
#include <cassert>
#include <iostream>

int main() {
  Protection p;
  assert(p.update(0,1,0,true,true,false)==0);
  assert(p.update(31,1,900,true,true,false)==1); // startup inrush blanked
  assert(p.update(100,1,900,true,true,false)==1);
  assert(p.update(132,1,800,true,true,false)==1);
  assert(p.update(281,1,800,true,true,false)==1);
  assert(p.update(282,1,800,true,true,false)==0);
  assert(p.fault==Fault::Overcurrent);
  assert(p.update(300,-1,0,true,true,true)==0); // reversing does not clear fault
  assert(p.update(310,0,0,true,true,true)==0); // held reset is not a fresh edge
  p.update(320,0,0,true,true,false);
  assert(p.update(330,0,0,true,true,true)==0);
  assert(p.fault==Fault::None);
  assert(p.update(361,-1,200,true,true,false)==-1);
  assert(p.update(400,1,200,true,true,false)==0);
  assert(p.update(429,1,200,true,true,false)==0);
  assert(p.update(430,1,200,true,true,false)==1);
  assert(p.update(30430,1,200,true,true,false)==0);
  assert(p.fault==Fault::Timeout);
  Protection q;
  q.update(31,1,200,true,true,false);
  q.update(200,1,800,true,true,false);
  q.update(300,1,100,true,true,false); // short current spike clears timer
  assert(q.update(400,1,800,true,true,false)==1);
  assert(q.update(549,1,800,true,true,false)==1);
  assert(q.update(550,1,800,true,true,false)==0);
  Protection r;
  assert(r.update(40,1,100,false,true,false)==0);
  assert(r.fault==Fault::Driver);
  Protection s;
  assert(s.update(40,1,0,true,false,false)==0);
  assert(s.fault==Fault::Sensor);
  // Verify millisecond counter wrap during a run.
  Protection w; w.stopped_at=0xffffffe0u;
  assert(w.update(0xfffffffeu,1,200,true,true,false)==1);
  assert(w.update(50,1,200,true,true,false)==1);
  std::cout << "PASS: inrush, sustained overload, spikes, latching, reset, reversal, timeout, faults, timer wrap\n";
}
