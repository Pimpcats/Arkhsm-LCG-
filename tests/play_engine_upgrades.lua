-- Result thresholds, helper skills and paid XP effects, then actual object order.
local passed=0
local function check(name, ok) assert(ok,name) ; passed=passed+1 end
local state={hour=1,dissonance=0,memory=0,stage=0,band="Calm"}
local R={G={n=2,phase="investigation",round=1,clock=0,inv={},enemies={},appointed={},locList={},acts={},
  knowledge={},metrics={tests=0,tests_passed=0,tokens={},cards_drawn=0,cards_played=0,draws_by={}}},CARDS={}}
local T={E={run=function() end},st=function() return state end,api=function() end}
dofile("tools/play_engine/lua/rules.lua")(R,T)
local FX=dofile("tools/play_engine/lua/effects.lua")(R,T)
local P=dofile("tools/play_engine/lua/players.lua")(R,T)
dofile("tools/play_engine/lua/flow.lua")(R,T)
local inv={id="fixture",name="fixture",assets={},hand={},deck={},discard={},resources=8,round={},loopUsed={},
  stats={wil=3,int=3,com=3,agi=3},memory=0,cardMemory=0,testedTypes={},failedTypes={},lastTurn={},loc="x",
  damage=0,horror=3,health=8,sanity=8}
R.G.inv={inv}
R.investigatorsAt=function() return {inv} end
R.locOf=function() return {guid="x"} end
R.syncAppointedArrival=function() end
R.checkReset=function() end
R.touch=function() end
R.log=function() end
T.returnTokens=function() end
T.drawToken=function() return "0",{} end
FX.tokenAfter=function() end
R.AI={prepareTest=function()
  return {{owner=inv,card={name="Deduction",level=2},icons=2},
          {owner={},card={name="Deduction",level=0},icons=1}},0
end}
local after=P.afterTest
P.afterTest=function() end
local ok,margin=R.test(inv,"int",4,{kind="investigate"})
check("skill contributions include every helper printing",ok and margin==2 and P.resultBonus(inv,"Deduction",margin)==3)
check("upgraded skills require the margin",P.resultBonus(inv,"Deduction",1)==2)
P.afterTest=after
local damage
R.test=function() return true,1,"0" end
R.damageEnemy=function(_,n) damage=n end
R.enemyFight=function() return 3 end
local enemy={id="enemy",loc="x",def={}}
for _,name in ipairs({"Switchblade (2)","Shotgun (4)"}) do
  inv.lastCommitted={}
  R.ACT.fight(inv,enemy,{name=name,uses=3})
  check(name.." low margin damage",damage==1)
end
local derringer={name=".41 Derringer (2)",uses=6}
R.ACT.fight(inv,enemy,derringer)
check("Derringer bonus starts at margin one",damage==2)
R.test=function() return true,3,"0" end
R.G.turnOf=inv ; inv.actionsLeft=1
R.ACT.fight(inv,enemy,derringer) ; R.ACT.fight(inv,enemy,derringer)
check("Derringer's additional action is once per turn",inv.actionsLeft==2)
R.G.turnOf={} ; R.ACT.fight(inv,enemy,derringer)
check("Derringer limit resets on the next turn",inv.actionsLeft==3)
R.test=function() return true,6,"0" end
R.ACT.fight(inv,enemy,{name="Shotgun (4)",uses=3})
check("Shotgun caps damage at five",damage==5)
inv.lastCommitted={["Vicious Blow"]={{level=2}}}
R.test=function() return true,2,"0" end
R.ACT.fight(inv,enemy,{name="Lightning Gun (5)",uses=3})
check("upgraded Vicious Blow modifies weapon result",damage==5)
inv.assets={{name="Higher Education (3)"}}
inv.hand={{},{},{},{}}
check("Higher Education respects hand condition",#P.boosts(inv,"int",{})==0)
inv.hand[5]={}
local b=P.boosts(inv,"int",{})[1]
b.pay()
check("Higher Education pays one for two",b.gain==2 and inv.resources==7)
inv.assets={{name="Streetwise (3)"}}
b=P.boosts(inv,"agi",{})[1] ; b.pay()
check("Streetwise pays two for three",b.gain==3 and inv.resources==5)
inv.assets={{name="Peter Sylvestre (2)"}}
check("Peter boosts both printed skills",P.staticBonus(inv,"wil",{})==1 and P.staticBonus(inv,"agi",{})==1)
inv.assets={}
inv.hand={{name="Opportunist",type="Skill",icons={wild=1},level=2}}
check("Opportunist cannot help another investigator",#P.commitables(inv,"int",{helper=true})==0)
local heal
R.heal=function(_,d,h) heal=h end
P.afterTest(inv,true,2,"wil",{},{{owner=inv,card={name="Fearless",level=2}}})
check("Fearless improves only at the printed margin",heal==2)
P.afterTest(inv,true,1,"wil",{},{{owner=inv,card={name="Fearless",level=2}}})
check("Fearless low margin heals one",heal==1)
inv.assets={{name="Knife",rec={name="Knife",slot="Hand"}}, {name="Flashlight",rec={name="Flashlight",slot="Hand"}}}
local gun={name="Shotgun (4)",slot="Hand x2",cost=0}
inv.hand={gun} ; P.playAsset(inv,gun)
check("two-slot assets replace both occupied hand slots",#inv.assets==1 and inv.assets[1].name==gun.name)
inv.assets={{name="Shrivelling",rec={name="Shrivelling",slot="Arcane"}}}
local spell={name="Shrivelling (3)",slot="Arcane",cost=0}
inv.hand={spell} ; P.playAsset(inv,spell)
check("two single-slot spells fit together",#inv.assets==2)

-- Run reordering on real emulator object data: faces, backs and IDs survive.
local E=dofile("tests/sced_real/tts_emu.lua")
E.srcDirs={} ; E.quiet=true ; E.loadSave({ObjectStates={}},"test")
local tablekit=dofile("tools/play_engine/lua/tablekit.lua")
tablekit.init({E=E})
local function card(g,id,rank)
  return {Name="CardCustom",GUID=g,CardID=id,GMNotes=E.J.encode({rank=rank}),
    CustomDeck={["1"]={FaceURL="https://example.test/face.jpg",BackURL="https://example.test/back.jpg"}}}
end
local data={Name="DeckCustom",GUID="abc123",DeckIDs={101,102,103,104},
  Transform={posX=0,posY=1,posZ=0},ContainedObjects={card("a00001",101,3),card("a00002",102,1),card("a00003",103,2),card("a00004",104,0)}}
local deck=E.spawnData(data,{},"test") ; E.run(0.2)
tablekit.encounterDeck=function() return E.G.getObjectFromGUID("abc123") end
check("reorder works on an actual Deck",tablekit.reorderEncounterTop(3,function(md) return md.rank end))
deck=tablekit.encounterDeck()
local d=deck.getData()
check("only top three are reordered",d.DeckIDs[1]==102 and d.DeckIDs[2]==103 and d.DeckIDs[3]==101 and d.DeckIDs[4]==104)
check("bottom move changes draw order",tablekit.moveTopEncounterBottom())
d=tablekit.encounterDeck().getData()
check("bottom move retains every card",#d.ContainedObjects==4 and d.DeckIDs[1]==103 and d.DeckIDs[4]==102)
local seen={}
for _,c in ipairs(d.ContainedObjects) do
  seen[c.GUID]=true
  check("card images survive "..c.GUID,c.CustomDeck["1"].FaceURL=="https://example.test/face.jpg" and c.CustomDeck["1"].BackURL=="https://example.test/back.jpg")
end
check("card GUIDs survive",seen.a00001 and seen.a00002 and seen.a00003 and seen.a00004 and #E.errors==0)
print(string.format("UPGRADE AND ORDER REGRESSIONS: %d passed",passed))
