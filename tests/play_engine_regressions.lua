-- Designer-only interaction regressions, using the actual engine modules.
local passed = 0
local function check(name, condition) assert(condition, name) ; passed = passed + 1 end
local state = { hour=1, dissonance=0, stage=0, band="Calm", memory=10 }
local calls = {}
local R = { G = { cfg={}, acts={}, locList={}, inv={}, enemies={}, knowledge={}, n=3, round=1, clock=0,
  metrics={attacks=0,damage=0,horror=0,damage_by={},horror_by={},memory_on_cards={},tests=0,tests_passed=0,tokens={},
  dissonance_sources={},diss_max=0,card_years=0} }, CARDS={} }
local T = {E={run=function() end},J={},st=function() return state end,
  api=function(name, p) calls[#calls+1]={name=name,p=p} end}
dofile("tools/play_engine/lua/rules.lua")(R,T)
local FX=dofile("tools/play_engine/lua/effects.lua")(R,T)
local P=dofile("tools/play_engine/lua/players.lua")(R,T)
dofile("tools/play_engine/lua/flow.lua")(R,T)
local function inv(id)
  return {id=id,name=id,loc="x",damage=0,horror=0,health=9,sanity=8,round={},loopUsed={},memory=0,cardMemory=0,
    assets={},hand={},deck={},discard={},threat={},lastTurn={},stats={wil=3,int=3,com=3,agi=3},resources=5,
    testedTypes={},failedTypes={}}
end
local elias,ayako,birdie=inv("sthrelias"),inv("sthrayako"),inv("sthrbirdie")
local L={guid="x",id="sthr-loc-belfry",district="Church"}
R.G.inv={elias,ayako,birdie}
R.locOf=function() return L end
R.locById=function(id) return id==L.id and L or nil end
local carry={id="sthr-act-whythirteen",holder=elias,completed=false}
check("arrival does not advance timed carry act", FX.canAdvance(carry)==nil)
R.G.acts.Church=carry
local advanced=0
R.advanceAct=function() advanced=advanced+1 end
FX.afterAdvance()
check("Hourglass advance resolves timed carry act", advanced==1)

-- Elias: when damage would be dealt to an investigator at his location, discard up to
-- 3 cards from the top of his deck and prevent 1 of it per card (once per round)
for k=1,20 do elias.deck[#elias.deck+1]={name="card "..k} end
R.hurt(ayako,3,0,"enemy attack")
check("Elias prevents damage to another investigator, 1 per card discarded",ayako.damage==0 and #elias.deck==17 and #elias.discard==3)
check("prevented damage needs no soak and leaves his own damage alone",elias.damage==0)
R.hurt(ayako,2,0,"enemy attack")
check("the prevention is limited once per round",ayako.damage==2 and #elias.deck==17)
elias.round={}
birdie.round.nobodyBelieves=true
R.hurt(birdie,2,0,"enemy attack")
check("Birdie's weakness blocks Elias affecting her",birdie.damage==2 and not elias.round.prevent and #elias.deck==17)
birdie.round.nobodyBelieves=nil
elias.deck={}
for k=1,4 do elias.deck[#elias.deck+1]={name="card "..k} end
R.hurt(elias,2,0,"enemy attack")
check("Elias keeps a few cards: with 4 in his deck he prevents nothing",elias.damage==2 and #elias.deck==4)
elias.damage,elias.round={},{}
elias.damage=0
elias.questUnlocked=false
check("the Memory reaction is on the quest back: not before it is met",R.investigatorMemory(elias)==0)
elias.questUnlocked=true
R.hurt(elias,1,0,"enemy attack")
check("after the quest is met, being dealt damage places 1 Memory",R.investigatorMemory(elias)==1)

elias.questUnlocked=false
elias.deck,elias.discard,elias.round,elias.damage={},{},{},0
elias.assets={ {name="Leather Coat",hp=2,sp=0,dmg=0,hor=0,rec={name="Leather Coat"}} }
R.G.inv={elias}
R.investigatorsAt=function() return {elias} end
FX.afterAttack=function() end
R.enemyAttack({id="enemy",name="enemy",def={damage=1,horror=0}},elias,"fixture")
check("a solo attack soaked by armor is not prevented without spare cards",elias.damage==0 and elias.assets[1].dmg==1)

local compass={name="Lucky Compass",memory=1}
birdie.assets={compass}
birdie.cardMemory,birdie.memory=3,4
check("there is no Memory save: an auto-fail still fails",P.wouldFail(birdie,-3,"Auto-fail",{important=true})==nil and birdie.cardMemory==3)
birdie.assets={}
R.syncMemory(birdie)
check("asset Memory leaves play with the asset",birdie.memory==3)

birdie.hand={{name="I Get Out"}}
birdie.damage,birdie.horror,birdie.actionsLeft=birdie.health,0,2
R.G.enemies,R.G.appointed={},{}
R.G.phase,R.G.turnOf="investigation",birdie
R.AI={chooseMove=function() return nil end}
check("defeat prevention plays",P.tryIGetOut(birdie))
check("defeat prevention only heals and ends own turn",birdie.damage==birdie.health-1 and birdie.horror==0 and birdie.actionsLeft==0)
check("I Get Out removes itself from the game: it is not in her discard pile",#birdie.discard==0 and #birdie.hand==0)

local muscle={name="Muscle Memory",type="Skill",traits="Recollection.",icons={wild=1}}
ayako.hand,ayako.testedTypes,ayako.years={muscle},{com=true},5
ayako.deck={{name="drawn before reveal"}}
local entry=P.commitables(ayako,"com",{})[1]
check("Weathered repeated combat receives three icons",entry.icons==3)
local committed={}
P.commit(ayako,entry,"com",{},committed)
check("Muscle Memory does not draw at commit time",#ayako.hand==0 and #ayako.deck==1)
P.afterTest(ayako,true,1,"com",{},committed)
check("Muscle Memory draws once on success",#ayako.hand==1 and #ayako.deck==0)

local fore={name="Foreknowledge",type="Skill",traits="Recollection.",icons={wild=2}}
local helper=inv("helper")
helper.hand,helper.deck={fore},{ {name="paid success draw"} }
helper.assets={{name="Notebook",memory=1}}
helper.memory=1
committed={}
P.commit(helper,P.commitables(helper,"int",{helper=true})[1],"int",{},committed)
check("helper pays own asset Memory",committed[1].memoryPaid and committed[1].icons==3 and helper.memory==0)
ayako.hand={fore}
check("Foreknowledge maximum applies across owners",P.commit(ayako,P.commitables(ayako,"int",{})[1],"int",{},committed)==nil and #ayako.hand==1)
P.afterTest(helper,true,1,"int",{},committed)
check("paid Foreknowledge draws on success",#helper.hand==1)

birdie.round.nobodyBelieves=true
local lamp=inv("lamp owner")
lamp.assets={{name="The Ambergrove Lamp"}}
R.investigatorsAt=function() return {birdie,lamp} end
check("weakness blocks another investigator's Lamp bonus",P.staticBonus(birdie,"agi",{kind="evade"})==0)
birdie.round.nobodyBelieves=nil
check("Lamp bonus returns after weakness expires",P.staticBonus(birdie,"agi",{kind="evade"})==1)

local cancellations=0
R.cancelAdvance=function() cancellations=cancellations+1 ; return true end
R.G.doom=4
R.advance(3,"skip")
check("one cancellation cancels the complete multi-Hour advance and clears doom",cancellations==1 and state.hour==1 and R.G.doom==0)

print(string.format("ENGINE REGRESSIONS: %d passed",passed))
