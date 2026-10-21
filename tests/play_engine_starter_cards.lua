-- The starter decks' player cards (docs/STARTER_DECKS.md) as the play engine encodes them.
local passed=0
local function check(name, ok) assert(ok,name) ; passed=passed+1 end
local state={hour=1,dissonance=0,memory=0,stage=0,band="Calm"}
local R={G={n=2,phase="investigation",round=1,clock=0,inv={},enemies={},appointed={},locList={},acts={},cfg={},
  knowledge={},metrics={tests=0,tests_passed=0,tokens={},cards_drawn=0,cards_played=0,draws_by={},attacks=0,damage=0,
  horror=0,damage_by={},horror_by={},evades=0}},CARDS={}}
local T={E={run=function() end,rand=function() return 0.5 end},J={},st=function() return state end,api=function() end}
dofile("tools/play_engine/lua/rules.lua")(R,T)
local FX=dofile("tools/play_engine/lua/effects.lua")(R,T)
local P=dofile("tools/play_engine/lua/players.lua")(R,T)
dofile("tools/play_engine/lua/flow.lua")(R,T)
local A=dofile("tools/play_engine/lua/ai.lua")(R,T)
local function newInv(id)
  return {id=id,name=id,assets={},hand={},deck={},discard={},resources=5,round={},loopUsed={},
    stats={wil=3,int=3,com=3,agi=3},memory=0,cardMemory=0,testedTypes={},failedTypes={},lastTurn={},loc="x",
    damage=0,horror=0,health=8,sanity=8,clues=0,clueTokens={},threat={}}
end
local inv,other=newInv("fixture"),newInv("other")
local L={guid="x",id="sthr-loc-test",name="Test",revealed=true,def={}}
R.G.inv={inv,other}
R.investigatorsAt=function() return {inv,other} end
R.locOf=function() return L end
R.syncAppointedArrival=function() end
R.checkReset=function() end
R.touch=function() end
R.placeEnemy=function() end
FX.onEvade=FX.onEvade or function() end
T.bagNames=function() return {"0","0","-1"} end
R.shroud=function() return 2 end
local clues=3
R.clues=function() return clues end
local found=0
R.discover=function(_,_,n) found=found+n end
local function card(name, t) t=t or {} ; t.name=name ; t.icons=t.icons or {} ; return t end
local function reset(x) x.assets,x.hand,x.deck,x.discard,x.round,x.damage,x.horror,x.resources={}, {}, {}, {}, {}, 0, 0, 5 end

-- Cunning: [int][agi], gaining one of each at 5 and at 10 resources
inv.hand={card("Cunning",{type="Skill",icons={int=1,agi=1}})}
inv.resources=4 ; check("Cunning below 5 resources",P.commitables(inv,"agi",{})[1].icons==1)
inv.resources=5 ; check("Cunning with 5 resources",P.commitables(inv,"int",{})[1].icons==2)
inv.resources=10 ; check("Cunning with 10 resources",P.commitables(inv,"agi",{})[1].icons==3)
check("Cunning has no [wil]",#P.commitables(inv,"wil",{})==0)

-- Silver Tongue: +1, or +2 on an evasion
inv.assets={{name="Silver Tongue",rec={}}}
check("Silver Tongue +2 on an evasion",P.boosts(inv,"agi",{kind="evade"})[1].gain==2)
check("Silver Tongue +1 investigating",P.boosts(inv,"int",{kind="investigate"})[1].gain==1)
check("Silver Tongue no [com]",#P.boosts(inv,"com",{kind="fight"})==0)

-- Improvised Shield: soaks 3 damage, then shuffles into the deck
reset(inv)
inv.hand={card("Improvised Shield",{type="Asset",slot="Hand",cost=1})}
local shield=inv.hand[1]
check("Improvised Shield is not played from hand",A.cardValue(inv,shield)==1)
inv.hand={} ; inv.discard={shield}
R.ACT.playFromDiscard(inv,shield)
check("Improvised Shield played from the discard pile",#inv.assets==1 and inv.assets[1].hp==3 and #inv.discard==0 and inv.resources==4)
R.hurt(inv,3,0,"test")
check("defeated Improvised Shield shuffles into the deck",#inv.assets==0 and #inv.discard==0 and inv.deck[1]==shield and inv.damage==0)

-- Jim Culver: +1 [wil]; after you take damage or horror, exhaust: draw 1
reset(inv)
inv.deck={card("Guts",{type="Skill"})}
inv.hand={card("Jim Culver",{type="Asset",slot="Ally",cost=4})}
P.playAsset(inv,inv.hand[1])
check("Jim Culver gives +1 [wil]",P.staticBonus(inv,"wil",{})==1)
R.hurt(inv,0,1,"test")
check("Jim's soak takes horror first and draws nothing",#inv.hand==0 and inv.assets[1].hor==1)
R.hurt(inv,0,1,"test",{direct=true})
check("Jim draws after you take horror",#inv.hand==1 and inv.assets[1].exhausted and inv.horror==1)

-- Medical Student / Art Student / Research Librarian enter play
reset(inv) ; reset(other)
other.damage,other.horror=2,2
inv.hand={card("Medical Student",{type="Asset",slot="Ally",cost=2})}
P.playAsset(inv,inv.hand[1])
check("Medical Student heals 1 damage and 1 horror",other.damage==1 and other.horror==1)
other.damage,other.horror=0,0
found=0
inv.hand={card("Art Student",{type="Asset",slot="Ally",cost=2})}
P.playAsset(inv,inv.hand[1])
check("Art Student discovers a clue and replaces the ally",found==1 and #inv.assets==1 and inv.assets[1].name=="Art Student")
inv.deck={card("Guts",{type="Skill"}),card("Encyclopedia (2)",{type="Asset",traits="Item. Tome."}),card("Dodge",{type="Event"})}
inv.hand={card("Research Librarian",{type="Asset",slot="Ally",cost=2})}
P.playAsset(inv,inv.hand[1])
check("Research Librarian finds a Tome",#inv.hand==1 and inv.hand[1].name=="Encyclopedia (2)" and #inv.deck==2)

-- investigation tools
local result={true,0,"0"}
local unpack_=table.unpack or unpack
R.test=function() return unpack_(result) end
reset(inv) ; found=0
local burglary={name="Burglary",rec={},uses=0}
inv.assets={burglary}
R.ACT.assetAbility(inv,burglary)
check("Burglary gains 3 resources instead of clues",inv.resources==8 and found==0 and burglary.exhausted)
local picks={name="Lockpicks",rec={slot="Hand"},uses=0}
inv.assets={picks} ; result={true,1,"0"}
R.ACT.assetAbility(inv,picks)
check("Lockpicks is discarded unless it succeeds by 2",#inv.assets==0 and inv.discard[#inv.discard]==picks.rec and found==1)
inv.assets={picks} ; picks.exhausted=false ; result={true,2,"0"}
R.ACT.assetAbility(inv,picks)
check("Lockpicks succeeding by 2 stays",#inv.assets==1)
local rite={name="Rite of Seeking",rec={slot="Arcane"},uses=3}
inv.assets={rite} ; inv.actionsLeft=2 ; found=0 ; result={true,0,"Skull"}
R.ACT.assetAbility(inv,rite)
check("Rite of Seeking discovers an additional clue",found==2 and rite.uses==2)
check("a symbol token ends the turn",inv.actionsLeft==0)
inv.actionsLeft=2 ; result={true,0,"-1"}
R.ACT.assetAbility(inv,rite)
check("a number token does not",inv.actionsLeft==2)
inv.hand={card("\"Look what I found!\"",{type="Event",cost=2})}
inv.resources=2 ; found=0 ; result={false,-2,"-3"}
R.ACT.investigate(inv,{})
check("\"Look what I found!\" after failing by 2",found==2 and #inv.hand==0 and inv.resources==0)
inv.hand={card("Read the Signs",{type="Event",cost=2})}
inv.resources=2 ; found=0 ; result={true,0,"0"}
local seenOpts
R.test=function(_,skill,_,o) seenOpts=o ; seenOpts.skill=skill ; return true,0,"0" end
R.ACT.play(inv,inv.hand[1])
check("Read the Signs adds [wil] and a clue",found==2 and seenOpts.bonus==3 and seenOpts.skill=="int")

-- fights and evasions from cards
local enemy={id="enemy",name="enemy",loc="x",def={fight=3,evade=3,health=4,damage=1,horror=1},damage=0}
R.G.enemies={enemy}
local dealt,diff
R.damageEnemy=function(_,n) dealt=n end
R.test=function(_,skill,d,o) diff=d ; seenOpts=o ; seenOpts.skill=skill ; return true,0,"0" end
local iw=card("Improvised Weapon",{type="Event",cost=1})
reset(inv) ; inv.discard={iw}
R.ACT.playFromDiscard(inv,iw,enemy)
check("Improvised Weapon from discard: -1 fight, +1 damage",diff==2 and dealt==2)
check("then shuffled into the deck",#inv.discard==0 and inv.deck[1]==iw and not iw.fromDiscard)
inv.hand={iw} ; inv.deck={}
R.ACT.play(inv,iw,enemy)
check("Improvised Weapon from hand deals 1 and is discarded",dealt==1 and inv.discard[1]==iw)
local bs=card("Backstab",{type="Event",cost=3})
inv.hand={bs}
R.ACT.play(inv,bs,enemy)
check("Backstab uses [agi] and deals +2",seenOpts.skill=="agi" and dealt==3)
local sb=card("Sneak By",{type="Event",cost=0})
inv.hand={sb} ; inv.resources=1 ; enemy.engaged=inv
R.ACT.play(inv,sb,enemy)
check("Sneak By gains 2 and evades",inv.resources==3 and enemy.exhausted and not enemy.engaged)
inv.assets={{name="Sticky Fingers",rec={}},{name="Stealth",rec={}}}
enemy.exhausted,enemy.engaged=false,inv
R.ACT.assetAbility(inv,inv.assets[2],nil,enemy)
check("Stealth: -2 evade, disengaged but ready",diff==1 and not enemy.engaged and not enemy.exhausted and enemy.noEngage==inv)
check("Sticky Fingers gains 1 after an evasion",inv.resources==4 and inv.assets[1].exhausted)
R.prey=function(_,c) return c[1] end
R.engageAt(L)
check("a Stealth-evaded enemy cannot engage you this turn",enemy.engaged==other)
enemy.engaged=nil ; R.investigatorsAt=function() return {inv} end
R.engageAt(L)
check("nor anyone else when you are alone",enemy.engaged==nil)
R.investigatorsAt=function() return {inv,other} end
enemy.noEngage=nil

-- "Get behind me!" / Heroic Rescue / Survival Knife
reset(inv) ; reset(other)
R.G.phase="enemy" ; R.G.round=2
enemy.def={fight=3,evade=3,health=4,damage=2,horror=1} ; enemy.damage,enemy.engaged,enemy.exhausted=0,other,false
other.health,other.damage=3,0
inv.hand={card("\"Get behind me!\"",{type="Event",cost=0})}
R.enemyAttack(enemy,other,"test")
check("\"Get behind me!\" takes the attack, 1 horror canceled",other.damage==0 and inv.damage==2 and inv.horror==0 and enemy.engaged==inv)
enemy.engaged=other
R.enemyAttack(enemy,other,"test")
check("and every attack there this phase",other.damage==0 and inv.damage==4)
inv.getBehind=nil ; inv.damage=0
inv.hand={card("Heroic Rescue",{type="Event",cost=1})} ; dealt=nil ; enemy.engaged=other
R.enemyAttack(enemy,other,"test")
check("Heroic Rescue takes the attack and deals 1 damage",other.damage==0 and inv.damage==2 and inv.horror==1 and dealt==1 and inv.resources==4)
inv.damage,inv.horror=0,0 ; dealt=nil
inv.assets={{name="Survival Knife",rec={slot="Hand"},uses=0}}
R.test=function(_,_,_,o) seenOpts=o ; return true,0,"0" end
enemy.engaged=inv
R.enemyAttack(enemy,inv,"test")
check("Survival Knife strikes back for 2 at +2",dealt==2 and seenOpts.bonus==1 and P.staticBonus(inv,"com",{weapon=inv.assets[1]})==1
  and inv.assets[1].exhausted)
R.G.phase="investigation"

-- skills: Take Heart, Eureka!, Defiance; Live and Learn
reset(inv)
inv.deck={card("a",{type="Skill"}),card("b",{type="Skill"}),card("c",{type="Skill"})}
P.afterTest(inv,false,-2,"int",{},{{owner=inv,card=card("Take Heart",{type="Skill"}),icons=0}})
check("Take Heart: draw 2, gain 2 after a failure",#inv.hand==2 and inv.resources==7)
inv.hand={} ; inv.deck={card("Dodge",{type="Event"}),card("Guts",{type="Skill",icons={wil=2}}),card("Paranoia",{weakness=true}),card("x",{type="Skill"})}
P.afterTest(inv,true,0,"int",{},{{owner=inv,card=card("Eureka!",{type="Skill"}),icons=3}})
check("Eureka! takes one of the top 3, never a weakness",#inv.hand==1 and inv.hand[1].name~="Paranoia" and #inv.deck==3)
local oldBag,oldValue=R.bag,FX.tokenValue
R.bag=function() return {"0","Skull","Cultist","Elder Sign"} end
FX.tokenValue=function(n) return ({Skull=-2,Cultist=-4,["0"]=0})[n] or 1 end
check("Defiance names the worst symbol in the bag",P.defianceSymbol(inv)=="Cultist")
R.bag,FX.tokenValue=oldBag,oldValue
inv.hand={card("Take Heart",{type="Skill"})}
local committed={}
P.takeHeart(inv,committed)
check("Take Heart commits to any test, once",#committed==1 and P.takeHeart(inv,committed)==nil)
inv.hand={card("Live and Learn",{type="Event",cost=0,icons={wild=1}})}
check("Live and Learn retries an important test",P.retryTest(inv,{important=true}) and #inv.hand==0)

-- Clarity of Mind / Meditative Trance; Hunter's Instinct; Scrounge for Supplies
reset(inv) ; reset(other)
other.horror=3
local clarity={name="Clarity of Mind",rec={slot="Arcane"},uses=3}
inv.assets={clarity}
R.ACT.assetAbility(inv,clarity,nil,A.mostHorrorHere(inv))
check("Clarity of Mind heals 1 horror",other.horror==2 and clarity.uses==2)
inv.assets={clarity,{name="Shrivelling",rec={slot="Arcane"},uses=4}}
inv.damage,inv.horror=1,2
inv.hand={card("Meditative Trance",{type="Event",cost=2})}
R.ACT.play(inv,inv.hand[1])
check("Meditative Trance heals one per filled arcane slot",inv.damage+inv.horror==1)
reset(inv)
local hunter={name="Hunter's Instinct",rec={},uses=1}
inv.assets={hunter}
inv.discard={card("Dodge",{type="Event"}),card("Guts",{type="Skill"})}
P.onEngaged(inv,enemy)
check("Hunter's Instinct returns an event, discarded with no supplies",#inv.hand==1 and inv.hand[1].name=="Dodge"
  and #inv.assets==0 and #inv.discard==2)
inv.hand={card("Scrounge for Supplies",{type="Event",cost=0})}
inv.discard={card("Paranoia",{weakness=true}),card("Machete",{type="Asset"}),card("Lucky!",{type="Event"})}
R.ACT.play(inv,inv.hand[1])
check("Scrounge for Supplies takes a level 0 card back",#inv.hand==1 and inv.hand[1].name~="Paranoia")

io.write("starter cards: ", passed, " checks passed\n")
