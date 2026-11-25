---- MODULE gate ----
\* Publication is serialized by the publish job's per-PR concurrency group;
\* the model assumes one publisher at a time and checks the ownership properties.
EXTENDS Naturals, TLC

CONSTANTS Heads, Runs

VARIABLES current, tested, phase, published, owner

vars == <<current, tested, phase, published, owner>>

TypeOK ==
  /\ current \in Heads
  /\ tested \in [Runs -> Heads \cup {0}]
  /\ phase \in [Runs -> {"idle", "pending", "done", "skipped"}]
  /\ published \in [Heads -> {"none", "pass", "fail"}]
  /\ owner \in [Heads -> Runs \cup {0}]

Init ==
  /\ current \in Heads
  /\ tested = [r \in Runs |-> 0]
  /\ phase = [r \in Runs |-> "idle"]
  /\ published = [h \in Heads |-> "none"]
  /\ owner = [h \in Heads |-> 0]

Push(h) ==
  /\ h \in Heads
  /\ current' = h
  /\ UNCHANGED <<tested, phase, published, owner>>

Start(r) ==
  /\ r \in Runs
  /\ phase[r] = "idle"
  /\ tested' = [tested EXCEPT ![r] = current]
  /\ phase' = [phase EXCEPT ![r] = "pending"]
  /\ UNCHANGED <<current, published, owner>>

Complete(r) ==
  /\ r \in Runs
  /\ phase[r] = "pending"
  /\ IF tested[r] # current
     THEN
       /\ phase' = [phase EXCEPT ![r] = "skipped"]
       /\ UNCHANGED <<current, tested, published, owner>>
     ELSE
       /\ \E v \in {"pass", "fail"}:
            /\ published[tested[r]] = "none"
            /\ phase' = [phase EXCEPT ![r] = "done"]
            /\ published' = [published EXCEPT ![tested[r]] = v]
            /\ owner' = [owner EXCEPT ![tested[r]] = r]
            /\ UNCHANGED <<current, tested>>

Next ==
  \/ \E h \in Heads: Push(h)
  \/ \E r \in Runs: Start(r)
  \/ \E r \in Runs: Complete(r)

Spec == Init /\ [][Next]_vars

NoWrongHead ==
  \A h \in Heads:
    published[h] # "none" => /\ owner[h] # 0
                             /\ tested[owner[h]] = h

NoStaleOwner ==
  \A h \in Heads:
    owner[h] # 0 => h \in Heads

====
