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

local coat={name="Leather Coat",hp=2,sp=0,dmg=0,hor=0,rec={name="Leather Coat"}}
elias.assets={coat}
R.hurt(ayako,2,0,"enemy attack")
check("redirected ordinary damage can be assigned to armor",elias.damage==0 and coat.dmg==2 and ayako.damage==0)
check("redirect reaction awards investigator Memory",R.investigatorMemory(elias)==1)
birdie.round.nobodyBelieves=true
elias.round={}
R.hurt(birdie,1,0,"enemy attack")
check("Birdie's weakness blocks Elias affecting her",birdie.damage==1 and not elias.round.redirect)
elias.assets={ {name="Guard Dog",hp=3,sp=1,dmg=0,hor=0,rec={name="Guard Dog"}} }
local retaliated=0
R.damageEnemy=function(_,n) retaliated=retaliated+n end
R.hurt(ayako,1,0,"enemy attack",{enemy={}})
check("redirection preserves attacking enemy context",retaliated==1)

elias.assets={ {name="Leather Coat",hp=2,sp=0,dmg=0,hor=0,rec={name="Leather Coat"}} }
elias.round={}
R.G.inv={elias}
R.investigatorsAt=function() return {elias} end
FX.afterAttack=function() end
local before=R.investigatorMemory(elias)
R.enemyAttack({id="enemy",name="enemy",def={damage=1,horror=0}},elias,"fixture")
check("solo reaction includes owned-asset damage",R.investigatorMemory(elias)==before+1 and elias.damage==0)

local compass={name="Lucky Compass",memory=1}
birdie.assets={compass}
birdie.cardMemory,birdie.memory=2,3
check("Birdie's investigator-only cost cannot use Compass Memory",P.wouldFail(birdie,-3,"Auto-fail",{important=true})==nil)
R.addMemory(birdie,1,"fixture")
check("Birdie can pay three investigator Memory",P.wouldFail(birdie,-3,"Auto-fail",{important=true})==0 and birdie.cardMemory==0 and compass.memory==1)
birdie.assets={}
R.syncMemory(birdie)
check("asset Memory leaves play with the asset",birdie.memory==0)

birdie.hand={{name="I Get Out"}}
birdie.damage,birdie.horror,birdie.actionsLeft=birdie.health,0,2
R.G.enemies,R.G.appointed={},{}
R.G.phase,R.G.turnOf="investigation",birdie
R.AI={chooseMove=function() return nil end}
check("defeat prevention plays",P.tryIGetOut(birdie))
check("defeat prevention only heals and ends own turn",birdie.damage==birdie.health-1 and birdie.horror==0 and birdie.actionsLeft==0)

local muscle={name="Muscle Memory",type="Skill",traits="Recollection.",icons={wild=1}}
ayako.hand,ayako.testedTypes,ayako.years={muscle},{com=true},5
ayako.deck={{name="drawn before reveal"}}
local entry=P.commitables(ayako,"com",{})[1]
check("Weathered repeated combat receives three icons",entry.icons==3)
local committed={}
P.commit(ayako,entry,"com",{},committed)
check("Muscle Memory draws at commit time",#ayako.hand==1 and #ayako.deck==0)
P.afterTest(ayako,true,1,"com",{},committed)
check("Muscle Memory does not draw twice",#ayako.hand==1)

local fore={name="Foreknowledge",type="Skill",traits="Recollection.",icons={wild=2}}
local helper=inv("helper")
helper.hand,helper.deck={fore},{ {name="paid success draw"} }
helper.assets={{name="Notebook",memory=1}}
helper.memory=1
committed={}
P.commit(helper,P.commitables(helper,"int",{helper=true})[1],"int",{},committed)
check("helper pays own asset Memory",committed[1].memoryPaid and committed[1].icons==4 and helper.memory==0)
ayako.hand={fore}
check("Foreknowledge maximum applies across owners",P.commit(ayako,P.commitables(ayako,"int",{})[1],"int",{},committed)==nil and #ayako.hand==1)
P.afterTest(helper,true,1,"int",{},committed)
check("paid Foreknowledge draws on success",#helper.hand==1)

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
