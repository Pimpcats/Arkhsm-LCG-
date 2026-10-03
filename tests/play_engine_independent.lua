-- SPOILERS: independent designer regressions against current engine modules.
-- No source mutation or table build. Expected behavior comes from effective
-- cards and the current guide, not from the root agent's regression fixture.
local passed, failed = 0, 0
local function expect(name, value)
  if value then passed = passed + 1; print("PASS " .. name)
  else failed = failed + 1; print("FAIL " .. name) end
end
local function case(name, fn)
  local ok, err = pcall(fn)
  if not ok then failed = failed + 1; print("ERROR " .. name .. ": " .. tostring(err)) end
end
local function fixture()
  local st = {hour=2,dissonance=0,stage=0,band="Calm",memory=10}
  local calls, released = {}, {}
  local m={damage=0,horror=0,attacks=0,appointed_attacks=0,aoo=0,tests=0,tests_passed=0,defeats=0,
    cards_played=0,weaknesses_drawn=0,card_years=0,diss_max=0,evades=0,holdback_attempts=0,
    holdbacks=0,rewinds=0,cancelled_advances=0,moves=0,crossings=0,crossing_hours=0,
    damage_by={},horror_by={},memory_on_cards={},tokens={},hour_sources={},dissonance_sources={},
    actions={},defeated={},defeated_by={},defeated_who={},doom_sources={},contest_sources={}}
  local R={G={cfg={},acts={},locList={},inv={},enemies={},knowledge={},n=3,round=1,clock=0,
    phase="investigation",appointed={exhausted=false},metrics=m},CARDS={}}
  local tokenNames={"0", "-2", "Static"}
  local entries={}
  for i,n in ipairs(tokenNames) do entries[i]={name=n,guid="tok"..i} end
  local bag={getObjects=function() return entries end,
    takeObject=function(p)
      for _,e in ipairs(entries) do if e.guid==p.guid then
        return {getName=function() return e.name end,getGUID=function() return e.guid end}
      end end
    end,putObject=function(o) released[#released+1]=o end}
  local T={E={run=function() end,rand=function() return 0 end},J={},st=function() return st end,
    api=function(n,p) calls[#calls+1]={name=n,p=p} end,
    dissonance=function(n) st.dissonance=st.dissonance+n end,
    ctl=function(n,right)
      if n=="Hour" then st.hour=st.hour+(right and -1 or 1)
      elseif n=="Appointed" then st.stage=st.stage+(right and -1 or 1) end
    end,
    click=function(_,n) if n=="Hold Back" then st.stage=math.max(0,st.stage-1);st.hour=st.hour-1 end end,
    chaosBag=function() return bag end,
    encounterDeck=function() return nil end,
    searchEncounter=function() return nil end,
    returnTokens=function() end,
    drawToken=function() return "0",bag.takeObject({guid="tok1"}) end}
  dofile("tools/play_engine/lua/rules.lua")(R,T)
  local FX=dofile("tools/play_engine/lua/effects.lua")(R,T)
  local P=dofile("tools/play_engine/lua/players.lua")(R,T)
  dofile("tools/play_engine/lua/flow.lua")(R,T)
  local AI=dofile("tools/play_engine/lua/ai.lua")(R,T)
  local loc={id="sthr-loc-belfry",guid="x",district="Church",revealed=true,closed=false,adj={},
    obj={getPosition=function() return {x=0,y=1,z=0} end}}
  R.locOf=function(i) return i and i.loc==loc.guid and loc or nil end
  R.locById=function(id) return id==loc.id and loc or nil end
  R.investigatorsAt=function(L)
    local out={}; for _,i in ipairs(R.G.inv) do if L and i.loc==L.guid and not i.defeated then out[#out+1]=i end end
    return out
  end
  R.syncAppointedArrival=function() end
  R.placeEnemy=function() end
  R.damageEnemy=function(e,n) e.damage=(e.damage or 0)+n end
  R.moveHourCard=function() end
  R.returnHourCard=function() end
  R.scanLocationsLight=function() end
  FX.onHourReached=function() end -- isolate advance hooks from Hour-card text
  R.prob=function() return 0 end
  R.checkObjectives=function() end
  R.appointedLoc=function() return loc end
  R.appointedCard=function() return {} end
  R.contest=function() end
  R.skillBase=function(i,s) return i.stats[s] end
  R.shroud=function() return 2 end
  R.clues=function() return 2 end
  R.moveInv=function(i,L) i.loc=L.guid end
  R.isCrossing=function() return false end
  FX.afterAttack=function() end
  FX.checkWakes=function() end
  FX.townHallFree=function() end
  R.SCEN={FACT_DISTRICT={}}
  local function investigator(id)
    local i={id=id,name=id,idx=#R.G.inv+1,loc="x",damage=0,horror=0,health=9,sanity=8,
      memory=0,cardMemory=0,assets={},hand={},deck={},discard={},threat={},round={},loopUsed={},
      clues=0,clueTokens={},
      lastTurn={},lastCommitted={},testedTypes={},failedTypes={},stats={wil=3,int=3,com=3,agi=3},resources=5,
      card={getPosition=function() return {x=0,y=1,z=0} end},color="White",actionsLeft=3}
    R.G.inv[#R.G.inv+1]=i
    return i
  end
  local function tally(kind,id)
    local n=0;for _,c in ipairs(calls) do if c.name=="shApiTally" and c.p.kind==kind and (not id or c.p.id==id) then n=n+c.p.delta end end
    return n
  end
  return R,P,FX,AI,T,st,investigator,loc,calls,released,tally
end

case("timed delivery matrix",function()
  local R,P,FX,AI,T,st,new,L=fixture();local i=new("sthrelias")
  local act={id="sthr-act-whythirteen",holder=i,completed=false};R.G.acts.Church=act
  local n=0;R.advanceAct=function() n=n+1 end
  expect("timed arrival waits",FX.canAdvance(act)==nil)
  R.cancelAdvance=function() return true end;R.G.doom=2;R.advance(3,"skip")
  expect("canceled skip advances neither clock nor delivery and clears doom",st.hour==2 and n==0 and R.G.doom==0)
  R.rewind(1,"fixture")
  expect("rewind does not deliver timed act",st.hour==1 and n==0)
  R.cancelAdvance=function() return false end;R.advance(1,"doom")
  expect("real Hourglass advance delivers",st.hour==2 and n==1)
  FX.ACTS["fixture-carry"]={carry={asset="fixture"},at=L.id}
  expect("untimed carry arrival still delivers",FX.canAdvance({id="fixture-carry",holder=i})~=nil)
end)

for _,which in ipairs({"ordinary","direct","prohibited"}) do
  case("redirection "..which,function()
    local R,P,FX,AI,T,st,new=fixture();local e,a=new("sthrelias"),new("sthrayako")
    local coat={name="Leather Coat",hp=3,sp=0,dmg=0,hor=0,rec={name="Leather Coat"}}
    e.assets={coat};if which=="prohibited" then a.round.nobodyBelieves=true end
    R.hurt(a,2,0,"fixture attack",{direct=which=="direct"})
    if which=="ordinary" then
      expect("redirect remains ordinary with eligible soak",e.damage==0 and coat.dmg==2 and a.damage==0)
      expect("redirect award belongs on investigator",e.cardMemory==1 and e.memory==1)
    else expect(which.." damage not redirected",a.damage==2 and e.memory==0 and coat.dmg==0) end
  end)
end
case("redirection context/no soak",function()
  local R,P,FX,AI,T,st,new=fixture();local e,a=new("sthrelias"),new("sthrayako")
  local enemy={damage=0};e.assets={{name="Guard Dog",hp=3,sp=1,dmg=0,hor=0,rec={name="Guard Dog"}}}
  R.hurt(a,1,0,"fixture attack",{enemy=enemy})
  expect("redirect preserves enemy for asset reaction",enemy.damage==1)
  e.round={};e.assets={};R.hurt(a,1,0,"fixture attack",{enemy=enemy})
  expect("redirect without asset damages recipient ordinarily",e.damage==1 and a.damage==0)
end)

for _,prevented in ipairs({false,true}) do
  case("lone damage reaction "..tostring(prevented),function()
    local R,P,FX,AI,T,st,new=fixture();local e=new("sthrelias")
    e.assets={{name="Leather Coat",hp=3,sp=0,dmg=0,hor=0,rec={name="Leather Coat"}}}
    if prevented then e.story={id="sthr-item-logbook"} end
    R.enemyAttack({id="fixture",name="fixture",def={damage=1,horror=0}},e,"fixture")
    expect(prevented and "fully prevented attack awards no Memory" or "owned-asset attack awards Memory",e.cardMemory==(prevented and 0 or 1))
    R.enemyAttack({id="fixture",name="fixture",def={damage=1,horror=0}},e,"fixture")
    expect("lone reaction places 1 Memory per damaging attack "..tostring(prevented),e.cardMemory==(prevented and 1 or 2))
  end)
end
case("special enemy lone reaction",function()
  local R,P,FX,AI,T,st,new=fixture();local e=new("sthrelias")
  e.assets={{name="Leather Coat",hp=3,sp=0,dmg=0,hor=0,rec={name="Leather Coat"}}}
  R.CARDS["sthr-appointed"]={damage=1,horror=0}
  R.appointedAttack(e,"fixture")
  expect("special enemy attack awards lone reaction for owned damage",e.cardMemory==1)
end)

case("Memory sources and thresholds",function()
  local R,P,FX,AI,T,st,new=fixture();local b,e,c=new("sthrbirdie"),new("sthrelias"),new("sthrcass")
  local compass={name="Lucky Compass",memory=1};b.assets={compass};b.cardMemory=2;R.syncMemory(b)
  expect("2 investigator plus 1 asset cannot pay investigator-only save",P.wouldFail(b,-2,"Auto-fail",{important=true})==nil)
  R.addMemory(b,1,"fixture");local saved=P.wouldFail(b,-2,"Auto-fail",{important=true})
  expect("3 investigator Memory pays without consuming asset",saved==0 and b.cardMemory==0 and compass.memory==1 and b.memory==1)
  e.assets={{name="Notebook",memory=3}};R.syncMemory(e)
  expect("asset Memory cannot improve investigator elder sign",P.elderSign(e)==1)
  c.assets={{name="Notebook",memory=3}};R.syncMemory(c);local before=c.resources;P.elderSignAfter(c,1)
  expect("asset Memory cannot pay investigator elder resources",c.resources==before)
  b.assets={};R.syncMemory(b)
  expect("departed asset Memory removed from aggregate",b.memory==0)
  e.cardMemory=3;e.damage=2;e.horror=2;R.syncMemory(e);R.G.knowledge["the-keepers-ninth-death"]=true
  P.elderSignAfter(e,3)
  expect("lasting elder heal resolves after actual damage heal",e.damage==1 and e.horror==1)
  e.damage=0;P.elderSignAfter(e,3)
  expect("lasting horror heal needs actual damage healed",e.horror==1)
end)
case("Memory discarded/replaced with asset",function()
  local R,P,FX,AI,T,st,new=fixture();local i=new("sthrayako")
  i.cardMemory=2;i.assets={{name="Leather Coat",hp=1,sp=0,dmg=0,hor=0,memory=3,rec={name="Leather Coat",slot="Body"}}};R.syncMemory(i)
  R.hurt(i,1,0,"fixture")
  expect("defeated asset loses only its own tokens",i.memory==2 and i.cardMemory==2)
  local old={name="Notebook",memory=2,rec={name="Notebook",slot="Hand"}}
  i.assets={old,{name="Flashlight",rec={name="Flashlight",slot="Hand"}}};R.syncMemory(i)
  local card={name="Magnifying Glass",type="Asset",cost=1,slot="Hand"};i.hand={card};P.playAsset(i,card)
  expect("slot replacement loses old asset tokens",i.memory==2 and i.assets[1].name=="Flashlight")
end)

for _,tracks in ipairs({{9,0},{0,8},{9,8}}) do
  case("defeat prevention "..tracks[1].."/"..tracks[2],function()
    local R,P,FX,AI,T,st,new=fixture();local b=new("sthrbirdie")
    b.damage,b.horror=tracks[1],tracks[2];b.hand={{name="I Get Out"}};b.assets={{name="Lucky Compass",memory=0}}
    R.G.turnOf=b;AI.chooseMove=function() return nil end
    expect("defeat prevention available "..tracks[1].."/"..tracks[2],P.tryIGetOut(b)==true)
    expect("defeat prevention only lowers injury "..tracks[1].."/"..tracks[2],b.damage==math.min(8,tracks[1]) and b.horror==math.min(7,tracks[2]))
    expect("defeat prevention ends own turn and adds asset Memory "..tracks[1].."/"..tracks[2],b.actionsLeft==0 and b.cardMemory==0 and b.assets[1].memory==1)
  end)
end
case("defeat prevention outside own turn",function()
  local R,P,FX,AI,T,st,new=fixture();local b,a=new("sthrbirdie"),new("sthrayako")
  b.damage=9;b.hand={{name="I Get Out"}};R.G.turnOf=a;AI.chooseMove=function() return nil end
  P.tryIGetOut(b)
  expect("off-turn save does not end another turn",b.actionsLeft==3 and a.actionsLeft==3)
end)

for _,skill in ipairs({"wil","com","agi"}) do
  for _,repeated in ipairs({false,true}) do
    case("Muscle matrix "..skill.."/"..tostring(repeated),function()
      local R,P,FX,AI,T,st,new=fixture();local i=new("sthrelias")
      local card={name="Muscle Memory",type="Skill",traits="Recollection.",icons={wild=1}}
      i.hand={card};i.deck={{name="draw"}};i.years=5;i.testedTypes[skill]=repeated
      local entry=P.commitables(i,skill,{})[1]
      local icons=1+(repeated and 1 or 0)+(skill~="wil" and 1 or 0)
      expect("Muscle correct icons "..skill.."/"..tostring(repeated),entry.icons==icons)
      local committed={};P.commit(i,entry,skill,{},committed)
      expect("Muscle no draw at commit "..skill.."/"..tostring(repeated),#i.hand==0)
      P.afterTest(i,false,-1,skill,{},committed)
      expect("Muscle no draw on a failed test "..skill.."/"..tostring(repeated),#i.hand==0)
      P.afterTest(i,true,1,skill,{},committed)
      expect("Muscle draws on success "..skill.."/"..tostring(repeated),#i.hand==(repeated and 1 or 0))
    end)
  end
end
for _,source in ipairs({"none","investigator","asset"}) do
  for _,success in ipairs({false,true}) do
    case("Foreknowledge matrix "..source.."/"..tostring(success),function()
      local R,P,FX,AI,T,st,new=fixture();local i,j=new("helper"),new("test owner")
      local card={name="Foreknowledge",type="Skill",traits="Recollection.",icons={wild=2}}
      i.hand={card};i.deck={{name="success draw"}}
      if source=="investigator" then i.cardMemory=1 elseif source=="asset" then i.assets={{name="Notebook",memory=1}} end
      R.syncMemory(i)
      local committed={};P.commit(i,P.commitables(i,"int",{helper=true})[1],"int",{},committed)
      expect("Foreknowledge cost/icons "..source.."/"..tostring(success),committed[1].icons==(source=="none" and 2 or 3) and i.memory==0)
      j.hand={card}
      expect("Foreknowledge max across owners "..source.."/"..tostring(success),P.commit(j,P.commitables(j,"int",{})[1],"int",{},committed)==nil and #j.hand==1)
      FX.afterFail=function() end;P.afterTest(j,success,success and 1 or -1,"int",{},committed)
      expect("Foreknowledge success draw "..source.."/"..tostring(success),#i.hand==((source~="none" and success) and 1 or 0))
    end)
  end
end

case("incoming/outgoing weakness scope",function()
  local R,P,FX,AI,T,st,new=fixture();local b,a=new("sthrbirdie"),new("sthrayako")
  b.round.nobodyBelieves=true
  local function guts() return {name="Guts",type="Skill",icons={wil=2}} end
  b.hand={guts()};local committed=AI.prepareTest(a,"wil",8,3,{})
  expect("affected investigator may commit outward",#committed==1 and committed[1].owner==b)
  b.hand={};a.hand={guts()};committed=AI.prepareTest(b,"wil",8,3,{})
  expect("other investigators cannot commit inward",#committed==0 and #a.hand==1)
  a.assets={{name="The Ambergrove Lamp"}}
  expect("other investigator passive blocked",P.staticBonus(b,"agi",{kind="evade"})==0)
  a.assets={};b.assets={{name="The Ambergrove Lamp"}}
  expect("own passive remains available",P.staticBonus(b,"agi",{kind="evade"})==1)
  b.assets={};b.damage=3
  R.ACT.assetAbility(a,{name="First Aid",uses=2})
  expect("another owner's heal cannot affect restricted investigator",b.damage==3)
  R.ACT.assetAbility(b,{name="First Aid",uses=2})
  expect("own healing still allowed",b.damage==2)
end)
case("Marked Deck asset-memory option and sealing",function()
  local R,P,FX,AI,T,st,new,L,calls,released,tally=fixture();local c=new("sthrcass")
  local a={name="Marked Deck",rec={name="Marked Deck",slot="Hand"}};local memoryAsset={name="Notebook",memory=1,rec={name="Notebook"}}
  c.assets={a,memoryAsset};R.syncMemory(c)
  local ok=P.markedDeck(c,a,"number")
  expect("Marked Deck number option can spend controlled-asset Memory",ok==true and memoryAsset.memory==0 and c.cardMemory==0)
  expect("Marked Deck paid costs tally and seal chosen number",tally("spent",c.id)==1 and tally("raises",c.id)==1 and c.sealedToken and c.sealedToken.getName()=="0")
end)
case("sealed asset departure",function()
  local R,P,FX,AI,T,st,new,L,calls,released=fixture();local c=new("sthrcass")
  local a={name="Marked Deck",rec={name="Marked Deck",slot="Hand"}}
  c.assets={a,{name="Flashlight",rec={name="Flashlight",slot="Hand"}}}
  P.markedDeck(c,a)
  local replacement={name="Switchblade",type="Asset",cost=1,slot="Hand"};c.hand={replacement};P.playAsset(c,replacement)
  expect("departing sealing asset releases its sealed token",c.sealedToken==nil and #released==1)
end)
case("Compass loop-power cost",function()
  local R,P,FX,AI,T,st,new,L,calls,released,tally=fixture();local b=new("sthrbirdie")
  local a={name="Lucky Compass",memory=1};b.assets={a};R.syncMemory(b)
  R.ACT.assetAbility(b,a,"jump",L)
  expect("Compass removes its asset token",a.memory==0 and b.cardMemory==0)
  expect("Compass token cost counts toward loop-power Years",tally("spent",b.id)==1)
end)
case("cannot-be-evaded condition",function()
  local R,P,FX,AI,T,st,new=fixture();local c=new("sthrcass")
  c.cardMemory=2;R.syncMemory(c)
  local en={id="sthr-housewins",name="The House Always Wins",loc="x",engaged=c,damage=0,def={traits="Humanoid. Criminal.",health=4}}
  R.G.enemies={en};local card={name="Rehearsed Escape",type="Event",cost=1};c.hand={card}
  expect("printed signature condition is active",R.cannotEvade(en)==true)
  R.ACT.play(c,card)
  expect("automatic evade cannot bypass cannot-be-evaded condition",not en.exhausted and en.engaged==c)
end)

case("investigator Memory reaction limits",function()
  local R,P,FX,AI,T,st,new=fixture();local i=new("sthrayako")
  P.afterTest(i,true,0,"int",{},{});P.afterTest(i,true,0,"int",{},{})
  expect("Ayako's reaction is limited twice per loop",i.memory==2)
  for _=1,4 do i.round={};P.afterTest(i,true,0,"int",{},{}) end
  expect("and no more than twice in a loop",i.memory==2)
  local b=new("sthrbirdie");P.afterTest(b,false,-1,"agi",{},{})
  expect("Birdie's reaction needs a failure by 2 or more",b.memory==0)
  P.afterTest(b,false,-2,"agi",{},{})
  expect("Birdie's reaction places 1 Memory",b.memory==1)
end)
case("Rehearsed Escape Elite choice once per loop",function()
  local R,P,FX,AI,T,st,new=fixture();local c=new("sthrbirdie");FX.onEvade=function() end
  local function elite() return {id="elite",name="Elite",loc="x",engaged=c,damage=0,def={traits="Monster. Elite.",health=5}} end
  local en=elite();R.G.enemies={en}
  R.ACT.play(c,{name="Rehearsed Escape",type="Event",cost=1})
  expect("first Elite evade raises Dissonance",en.exhausted and st.dissonance==1)
  local en2=elite();R.G.enemies={en2}
  expect("the Elite choice is spent for the loop",not P.rehearsedLegal(c,en2))
  R.ACT.play(c,{name="Rehearsed Escape",type="Event",cost=1})
  expect("second Elite evade is not legal",not en2.exhausted and en2.engaged==c and st.dissonance==1)
end)
case("multi-Hour charge timing",function()
  local R,P,FX,AI,T,st,new=fixture();local i=new("sthrelias")
  local a={name="Stolen Minute",uses=0};i.assets={a};R.cancelAdvance=function() return false end
  R.cancelAdvance=function() return true end;R.advance(1,"canceled")
  expect("canceled advance gives no charge",a.uses==0 and not i.loopUsed.stolenMinute)
  R.cancelAdvance=function() return false end;R.advance(2,"skip")
  expect("one multi-Hour advance recharges Stolen Minute once",st.hour==4 and a.uses==1)
  R.advance(1,"doom")
  expect("the recharge is limited once per loop",a.uses==1)
  local j=new("sthrayako");local b={name="Stolen Minute",uses=2};j.assets={b};i.assets={}
  R.advance(1,"doom")
  expect("a full Stolen Minute (maximum 2) does not spend the loop's recharge",b.uses==2 and not j.loopUsed.stolenMinute)
  b.uses=1;R.advance(1,"doom")
  expect("then the next advance recharges it",b.uses==2 and j.loopUsed.stolenMinute)
end)
case("purchased actions and repeat costs",function()
  local R,P,FX,AI,T,st,new,L,calls,released,tally=fixture();local i=new("sthrayako")
  local a={name="Stolen Minute",uses=2,exhausted=false};i.assets={a};i.hand={{name="The Same Doorway Twice",cost=1,traits="Recollection."}}
  R.G.turnOf=i;R.ACT.assetAbility(i,a)
  expect("Doorway repeats additional action without extra action/exhaust",i.actionsLeft==5 and a.uses==0 and a.exhausted)
  expect("Doorway pays resource/Dissonance costs",i.resources==4 and st.dissonance==1 and tally("raises",i.id)==1)
  i.hand={{name="The Same Doorway Twice",cost=1}};R.ACT.assetAbility(i,{name="Stolen Minute",uses=1})
  expect("Doorway cannot repeat without remaining charge",#i.hand==1)
end)
case("Notebook Knowledge reward owns asset Memory",function()
  local R,P,FX,AI,T,st,new=fixture();local i=new("sthrayako")
  local a={name="Cassandra's Notebook"};i.assets={a};i.deck={{name="one"},{name="two"}}
  P.onKnowledge("new entry")
  expect("Notebook draws two and gains two resources",#i.hand==2 and i.resources==7)
  expect("Notebook Knowledge Memory belongs on its asset",a.memory==1 and i.cardMemory==0 and i.memory==1)
end)
case("permanent setup",function()
  local R,P,FX,AI,T,st,new=fixture()
  R.CARDS["sthrayako"]={name="Ayako",wil=4,int=4,com=2,agi=2,health=5,sanity=8}
  local cards={{name="Anchor Point",permanent=true}}
  for j=1,30 do cards[#cards+1]={name="card "..j} end
  local i=P.newInvestigator(1,"sthrayako","White",{},nil,nil,{cards=cards,signatures={}},nil)
  expect("Anchor Point starts in play outside shuffled deck",#i.assets==1 and i.assets[1].name=="Anchor Point" and #i.hand==5 and #i.deck==25)
  expect("Anchor Point increases maximum sanity",i.sanity==9)
end)
for _,bank in ipairs({0,1,3,12}) do
  case("banked-memory weakness "..bank,function()
    local R,P,FX,AI,T,st,new=fixture();local i=new("sthrayako");st.memory=bank
    P.weakness(i,{id="sthr-untranslatable",name="Untranslatable"})
    expect("banked-memory weakness ceiling/cap "..bank,i.horror==math.min(5,math.ceil(bank/2)))
  end)
end
for _,spec in ipairs({{"Calm",0,1,0},{"Glitch",1,0,2},{"Noticed",2,0,0},{"Noticed",3,0,2}}) do
  case("band weakness "..spec[1].."/"..spec[2],function()
    local R,P,FX,AI,T,st,new=fixture();local i=new("sthrseraphine");st.band=spec[1];st.stage=spec[2]
    P.weakness(i,{id="sthr-debtofhours",name="The Debt of Hours"})
    expect("band weakness correct effect "..spec[1].."/"..spec[2],st.dissonance==spec[3] and i.horror==spec[4] and st.stage==(spec[1]=="Noticed" and spec[2]==2 and 3 or spec[2]))
  end)
end
case("specific investigator-memory weakness",function()
  local R,P,FX,AI,T,st,new=fixture();local i=new("sthrelias")
  i.assets={{name="Notebook",memory=4}};R.syncMemory(i)
  P.weakness(i,{id="sthr-eighthgrave",name="The Eighth Grave"})
  expect("investigator-only weakness does not count asset tokens",i.horror==2)
  i.cardMemory=1;R.syncMemory(i);i.horror=0
  P.weakness(i,{id="sthr-eighthgrave",name="The Eighth Grave"})
  expect("investigator-only weakness counts exactly its own tokens",i.horror==1)
end)
case("defeated investigator seal",function()
  local R,P,FX,AI,T,st,new,L,calls,released=fixture();local c,a=new("sthrcass"),new("sthrayako")
  local asset={name="Marked Deck",rec={name="Marked Deck",slot="Hand"}};c.assets={asset};c.cardMemory=2;R.syncMemory(c)
  P.markedDeck(c,asset)
  T.alive=function() return false end;R.endLoop=function() R.G.ended=true end
  R.defeat(c,"fixture",{})
  expect("elimination releases the unused seal",c.sealedToken==nil and #released==1)
  expect("elimination preserves the campaign Memory banking exception",c.memory==2 and c.cardMemory==2)
end)
for _,n in ipairs({1,2,3,4}) do
  case("full fare cost "..n,function()
    local R,P,FX,AI,T,st,new,L=fixture();dofile("tools/play_engine/lua/finale.lua")(R,T)
    R.G.n=n;R.CARDS["sthr-act-bargain"]={clues=5,clues_per_investigator=true};L.id="sthr-loc-ticketbooth"
    local i=new("sthrcass");i.resources=3
    local advanced=0;R.advanceAct=function() advanced=advanced+1 end
    R.objectiveAction(i,{id="sthr-act-bargain"})
    expect("unaffordable fare cannot start or partially pay at "..n,advanced==0 and i.resources==3)
    i.resources=5*n*3;R.objectiveAction(i,{id="sthr-act-bargain"})
    expect("full fare pays printed scale at "..n,advanced==1 and i.resources==0)
  end)
end
case("investigator boost repeat through policy",function()
  local R,P,FX,AI,T,st,new,L,calls,released,tally=fixture();local i=new("sthrseraphine")
  R.G.turnOf=i;i.hand={{name="The Same Doorway Twice",type="Event",cost=1,traits="Recollection."}}
  local committed,boost=AI.prepareTest(i,"wil",8,3,{important=true})
  expect("Seraphine repeated skill ability supplies both +2 bonuses",boost==4)
  expect("Seraphine repeated ability pays both costs and awards Memory for each of the three raises (limit 3 per loop)",st.dissonance==3 and i.round.sera==2 and i.cardMemory==3 and tally("raises",i.id)==3)
end)
case("secret boost repeat through policy",function()
  local R,P,FX,AI,T,st,new=fixture();local i=new("sthrayako")
  R.G.turnOf=i;i.assets={{name="The Lexicon of the Hour",uses=3,exhausted=false}}
  i.hand={{name="The Same Doorway Twice",type="Event",cost=1,traits="Recollection."}}
  local committed,boost=AI.prepareTest(i,"int",8,3,{important=true})
  expect("Lexicon repeat supplies both skill bonuses",boost==4 and i.assets[1].uses==1 and i.assets[1].exhausted)
end)
case("additional-action and ready choices",function()
  local R,P,FX,AI,T,st,new=fixture();local i=new("sthrseraphine");R.G.turnOf=i
  local a={name="Spell fixture",exhausted=true,rec={traits="Spell."}};i.assets={a}
  P.seraphine(i,"ready",a)
  expect("Seraphine may ready her Spell",not a.exhausted and i.round.sera==1)
  P.seraphine(i,"action")
  expect("Seraphine may gain action and earns Memory for each raise",i.actionsLeft==4 and i.round.sera==2 and i.cardMemory==2)
  expect("Seraphine further boosts unavailable at printed limit",#P.boosts(i,"wil",{})==0)
end)
case("Knowledge reaction repeat",function()
  local R,P,FX,AI,T,st,new=fixture();local i=new("sthrayako");R.G.turnOf=i
  local a={name="Cassandra's Notebook"};i.assets={a}
  i.deck={{name="one"},{name="two"},{name="three"},{name="four"}}
  i.hand={{name="The Same Doorway Twice",cost=1,type="Event",traits="Recollection."}}
  P.onKnowledge("new entry")
  expect("Doorway can repeat unlimited owned Knowledge reaction during own turn",#i.hand==4 and i.resources==8 and a.memory==2 and st.dissonance==1)
end)
for _,own in ipairs({false,true}) do
  case("most-recent-turn paid cost history "..tostring(own),function()
    local R,P,FX,AI,T,st,new=fixture();local i,j=new("sthrcass"),new("sthrayako")
    R.G.turnOf=own and i or j
    R.raise(1,"signature (cost)",i)
    R.test=function() return false end
    FX.ENC["sthr-loopnotices"](i)
    expect("encounter paid-cost penalty respects own-turn history "..tostring(own),st.dissonance==(own and 3 or 2))
  end)
end
for _,firstSuccess in ipairs({false,true}) do
  case("evade repeat current target legality "..tostring(firstSuccess),function()
    local R,P,FX,AI,T,st,new=fixture();local i=new("sthrseraphine");R.G.turnOf=i
    local a={name="The Bell of Ambergrove",uses=3,exhausted=false};i.assets={a};i.horror=2
    local en={id="fixture",name="fixture",engaged=i,loc="x",def={evade=2},damage=0};R.G.enemies={en}
    i.hand={{name="The Same Doorway Twice",type="Event",cost=1,traits="Recollection."}}
    local tests=0;R.test=function() tests=tests+1;return tests>1 or firstSuccess end
    FX.onEvade=function() end
    R.ACT.assetAbility(i,a,"evade",en)
    if firstSuccess then
      expect("successful evasion cannot repeat against disengaged target",tests==1 and a.uses==2 and #i.hand==1 and i.horror==1)
    else expect("failed evasion can repeat against still-engaged target",tests==2 and a.uses==1 and #i.hand==0 and i.horror==1) end
  end)
end
for _,cancel in ipairs({false,true}) do
  case("reset during token resolution "..tostring(cancel),function()
    local R,P,FX,AI,T,st,new=fixture();local i=new("sthrayako");st.dissonance=23
    if cancel then i.story={id="sthr-item-almanac"} end
    local draws=0
    T.drawToken=function()
      draws=draws+1
      local name=draws==1 and "Static" or "0"
      return name,{getName=function() return name end,getGUID=function() return "fixture"..draws end}
    end
    local original=T.api
    T.api=function(name,p)
      original(name,p)
      if name=="shApiResolveStatic" and not p.cancel then st.dissonance=st.dissonance+1 end
    end
    R.endLoop=function() R.G.ended=true end
    AI.prepareTest=function() return {},0 end
    local ok=R.test(i,"int",0,{important=true})
    if cancel then
      expect("canceled Static at reset boundary continues test without ending",ok and not R.G.ended and st.dissonance==23 and i.cardMemory==1)
    else expect("resolved reset-boundary Static aborts success and Memory award",R.G.ended and not ok and i.cardMemory==0) end
  end)
end

print(string.format("INDEPENDENT FIX PASS 3: %d passed, %d failed",passed,failed))
if failed>0 then os.exit(1) end
