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
  FX.onEvade=function() end -- hook installed by finale.lua in the full engine
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


-- New scope: printed XP cards and actual object order, independently specified.
for _,name in ipairs({"Deduction","Vicious Blow"}) do
  for _,margin in ipairs({0,1,2,4}) do
    case(name.." contributions margin "..margin,function()
      local R,P,FX,AI,T,st,new,L=fixture();local i,h1,h2=new("fixture"),new("helper1"),new("helper2")
      local skill=name=="Deduction" and "int" or "com"
      local contributions={{owner=i,card={name=name,level=2},icons=2},
        {owner=h1,card={name=name,level=2},icons=2},{owner=h2,card={name=name,level=0},icons=1}}
      R.AI.prepareTest=function() return contributions,0 end
      local difficulty=8-margin
      local amount=0
      if name=="Deduction" then
        R.shroud=function() return difficulty end;R.discover=function(who,_,n) expect("clue reward belongs to test taker "..margin,who==i);amount=n end
        R.ACT.investigate(i)
      else
        R.enemyFight=function() return difficulty end;R.damageEnemy=function(_,n,who) expect("damage credited to test taker "..margin,who==i);amount=n end
        R.ACT.fight(i,{id="fixture",loc="x",def={fight=difficulty}},nil)
      end
      expect(name.." every own/helper copy modifies result "..margin,amount==(margin>=2 and 6 or 4))
      expect(name.." committed cards discarded by their owners "..margin,#i.discard==1 and #h1.discard==1 and #h2.discard==1)
    end)
  end
end
case("skill contributions give nothing on failure",function()
  local R,P,FX,AI,T,st,new=fixture();local i,h=new("fixture"),new("helper")
  R.AI.prepareTest=function() return {{owner=h,card={name="Vicious Blow",level=2},icons=2}},0 end
  T.drawToken=function() return "Auto-fail",nil end
  local n=0;R.damageEnemy=function() n=n+1 end
  R.ACT.fight(i,{id="fixture",loc="x",def={fight=3}},nil)
  expect("no Vicious Blow damage on auto-fail",n==0)
end)
for name,skill in pairs({Guts="wil",Perception="int",Overpower="com",["Manual Dexterity"]="agi",["Unexpected Courage"]="wil"}) do
  case("printed shared maximum "..name,function()
    local R,P,FX,AI,T,st,new=fixture();local i,h=new("fixture"),new("helper")
    local c1,c2={name=name,type="Skill",icons={[skill]=2}},{name=name,type="Skill",icons={[skill]=2}}
    i.hand={c1};h.hand={c2};local shared={}
    expect(name.." first commit accepted",P.commit(i,{card=c1,icons=2},skill,{},shared)~=nil)
    expect(name.." helper duplicate barred without discarding",P.commit(h,{card=c2,icons=2},skill,{helper=true},shared)==nil and #h.hand==1 and #shared==1)
  end)
end
for _,name in ipairs({"Deduction","Vicious Blow","Survival Instinct"}) do
  case("unlimited skill "..name,function()
    local R,P,FX,AI,T,st,new=fixture();local i,h=new("fixture"),new("helper")
    local c1,c2={name=name,type="Skill"},{name=name,type="Skill"};i.hand={c1};h.hand={c2};local shared={}
    P.commit(i,{card=c1,icons=1},"agi",{},shared)
    expect(name.." duplicate is legal",P.commit(h,{card=c2,icons=1},"agi",{helper=true},shared)~=nil and #shared==2)
  end)
end
case("permanent setup",function()
  local R,P,FX,AI,T,st,new=fixture()
  R.CARDS.fixture={name="fixture",wil=3,int=3,com=3,agi=3,health=8,sanity=8}
  R.shuffle=function(x) return x end
  local cards={};for n=1,30 do cards[n]={name="ordinary "..n} end
  cards[#cards+1]={name="Higher Education (3)",permanent=true}
  cards[#cards+1]={name="Anchor Point",permanent=true}
  local sig={name="signature"};local weakness={name="weakness",weakness=true}
  local i=P.newInvestigator(1,"fixture","White",{},nil,nil,{cards=cards,signatures={sig}},weakness)
  expect("permanents start outside draw pile",#i.assets==2 and #i.hand==5 and #i.deck==27)
  expect("Anchor only adds its sanity",i.sanity==9 and i.health==8)
  local seen={};for _,c in ipairs(i.hand) do seen[c.name]=true end;for _,c in ipairs(i.deck) do seen[c.name]=true end
  expect("permanent never drawn; signatures and weakness retained",not seen["Higher Education (3)"] and not seen["Anchor Point"] and seen.signature and seen.weakness)
end)
case("Peter printed soak and recovery",function()
  local R,P,FX,AI,T,st,new=fixture();local i=new("fixture")
  local c={name="Peter Sylvestre (2)",cost=0,slot="Ally",level=2};i.hand={c};local a=P.playAsset(i,c)
  expect("Peter2 printed health1 sanity3",a.hp==1 and a.sp==3)
  a.hor=2;P.endTurn(i)
  expect("Peter recovery after own turn",a.hor==1)
  expect("Peter both static bonuses",P.staticBonus(i,"wil",{})==1 and P.staticBonus(i,"agi",{})==1)
end)
case("Encyclopedia phase duration",function()
  local R,P,FX,AI,T,st,new=fixture();local i,h=new("fixture"),new("helper")
  local a={name="Encyclopedia (2)",exhausted=false};i.assets={a}
  R.ACT.assetAbility(i,a,"int",h)
  expect("Encyclopedia paid action ability exhausts",a.exhausted and P.staticBonus(h,"int",{})==2 and P.staticBonus(h,"wil",{})==0)
  R.G.phase="enemy"
  expect("Encyclopedia expires at end of phase",P.staticBonus(h,"int",{})==0)
end)
case("asset slot capacity",function()
  local R,P,FX,AI,T,st,new=fixture();local i=new("fixture")
  i.assets={{name="Knife",rec={name="Knife",slot="Hand"}}, {name="Flashlight",rec={name="Flashlight",slot="Hand"}},
    {name="coat",rec={name="coat",slot="Body"}}}
  local gun={name="Shotgun (4)",slot="Hand x2",cost=0};i.hand={gun};P.playAsset(i,gun)
  expect("two-handed asset frees two slots and preserves other slot",#i.assets==2 and i.assets[1].name=="coat" and #i.discard==2)
  i.assets={{name="Shrivelling",rec={name="Shrivelling",slot="Arcane"}}}
  local spell={name="Shrivelling (3)",slot="Arcane",cost=0};i.hand={spell};P.playAsset(i,spell)
  expect("two single arcane cards remain",#i.assets==2)
  local double={name="Double spell",slot="Arcane x2",cost=0};i.hand={double};P.playAsset(i,double)
  expect("double arcane replaces both single spells",#i.assets==1 and i.assets[1].name=="Double spell")
end)
case("weapon printed thresholds",function()
  local R,P,FX,AI,T,st,new=fixture();local i=new("fixture");R.G.turnOf=i
  local enemy={id="fixture",loc="x",def={fight=3}};local dealt
  R.damageEnemy=function(_,n) dealt=n end
  local matrix={
    {".41 Derringer (2)",0,1},{".41 Derringer (2)",1,2},{".41 Derringer (2)",2,2},
    {"Switchblade (2)",0,1},{"Switchblade (2)",1,1},{"Switchblade (2)",2,2},
    {"Shotgun (4)",0,1},{"Shotgun (4)",1,1},{"Shotgun (4)",2,2},{"Shotgun (4)",5,5},{"Shotgun (4)",8,5}}
  for _,v in ipairs(matrix) do
    R.test=function() return true,v[2],"0" end;i.lastCommitted={};R.ACT.fight(i,enemy,{name=v[1],uses=5})
    expect(v[1].." printed damage at margin "..v[2],dealt==v[3])
  end
  local gun={name=".41 Derringer (2)",uses=8};R.test=function() return true,3,"0" end;i.actionsLeft=0
  R.ACT.fight(i,enemy,gun);expect("Derringer margin3 extra action",i.actionsLeft==1)
  R.ACT.fight(i,enemy,gun);expect("Derringer once per turn per asset",i.actionsLeft==1)
  R.G.round=2;R.ACT.fight(i,enemy,gun);expect("Derringer reusable next turn",i.actionsLeft==2)
end)
case("Shrivelling printed boost distinction",function()
  local R,P,FX,AI,T,st,new=fixture();local i=new("fixture")
  expect("Shrivelling0 has no skill bonus",P.staticBonus(i,"wil",{weapon={name="Shrivelling"}})==0)
  expect("Shrivelling3 adds2",P.staticBonus(i,"wil",{weapon={name="Shrivelling (3)"}})==2)
  expect("Shrivelling5 adds3",P.staticBonus(i,"wil",{weapon={name="Shrivelling (5)"}})==3)
end)
for _,level in ipairs({0,2}) do
 for _,helper in ipairs({false,true}) do
  case("Survival Instinct recipient "..level.." helper="..tostring(helper),function()
    local R,P,FX,AI,T,st,new=fixture();local i,h=new("fixture"),new("helper")
    local primary,other,notOurs={id="primary",engaged=i},{id="other",engaged=i},{id="otherowner",engaged=h}
    R.G.enemies={primary,other,notOurs}
    P.afterTest(i,true,1,"agi",{kind="evade",enemy=primary},{{owner=helper and h or i,card={name="Survival Instinct",level=level}}})
    expect("Survival excludes primary and other owner "..level..tostring(helper),primary.engaged==i and notOurs.engaged==h)
    expect("Survival effects belong to test taker "..level..tostring(helper),other.engaged==nil and (level==0 and not other.exhausted or level==2 and other.exhausted))
    expect("Survival committed card discarded to correct owner "..level..tostring(helper),#(helper and h or i).discard==1)
  end)
 end
end
case("Survival cannot-evade and failure guards",function()
  local R,P,FX,AI,T,st,new=fixture();local i,h=new("fixture"),new("helper")
  local primary,other={id="primary",engaged=i},{id="barred",engaged=i};R.G.enemies={primary,other}
  R.cannotEvade=function(en) return en.id=="barred" end
  P.afterTest(i,true,1,"agi",{kind="evade",enemy=primary},{{owner=h,card={name="Survival Instinct",level=2}}})
  expect("Survival2 respects cannot be evaded",other.engaged==i and not other.exhausted)
  P.afterTest(i,false,-1,"agi",{kind="evade",enemy=primary},{{owner=h,card={name="Survival Instinct",level=2}}})
  expect("Survival no effect after failure",other.engaged==i and not other.exhausted)
end)
for _,level in ipairs({0,2}) do
 for _,success in ipairs({false,true}) do
  case("Blinding badsymbol "..level.." success="..tostring(success),function()
    local R,P,FX,AI,T,st,new=fixture();local i=new("fixture");i.actionsLeft=2
    local enemy={id="enemy",loc="x",engaged=i,def={evade=3}};R.G.enemies={enemy}
    R.test=function() return success,success and 1 or -1,"Skull" end
    local c={name="Blinding Light",level=level,cost=0,type="Event"};i.hand={c}
    local hurt=0;R.hurt=function(_,_,h) hurt=hurt+h end
    R.ACT.play(i,c,enemy)
    expect("Blinding symbol loses action "..level..tostring(success),i.actionsLeft==1)
    expect("Blinding2 symbol horror only "..level..tostring(success),hurt==(level==2 and 1 or 0))
    expect("Blinding success damage by printing "..level..tostring(success),(enemy.damage or 0)==(success and (level==2 and 2 or 1) or 0))
  end)
 end
end
case("actual encounter draw order",function()
  local E=dofile("tests/sced_real/tts_emu.lua");E.srcDirs={};E.quiet=true;E.loadSave({ObjectStates={}},"test")
  local TT=dofile("tools/play_engine/lua/tablekit.lua");TT.init({E=E})
  local function card(g,id,rank)
    return {Name="CardCustom",GUID=g,CardID=id,Nickname=g,GMNotes=E.J.encode({rank=rank,id=g}),
      CustomDeck={["1"]={FaceURL="https://example.test/"..g..".jpg",BackURL="https://example.test/back.jpg"}}}
  end
  local d={Name="DeckCustom",GUID="c0ffee",DeckIDs={101,102,103,104},Transform={posX=2,posY=1,posZ=3},
    ContainedObjects={card("a00001",101,3),card("a00002",102,1),card("a00003",103,1),card("a00004",104,0)}}
  E.spawnData(d,{},"test");E.run(.2);TT.encounterDeck=function() return E.G.getObjectFromGUID("c0ffee") end
  expect("top3 reorder succeeds",TT.reorderEncounterTop(3,function(md) return md.rank end))
  local o=TT.encounterDeck();local x=o.getData()
  expect("stable equal-score order and untouched rest",x.DeckIDs[1]==102 and x.DeckIDs[2]==103 and x.DeckIDs[3]==101 and x.DeckIDs[4]==104)
  expect("position preserved",o.getPosition().x==2 and o.getPosition().z==3)
  expect("move first to bottom succeeds",TT.moveTopEncounterBottom())
  local expected={"a00003","a00001","a00004"};o=TT.encounterDeck()
  for n,g in ipairs(expected) do
    local c=o.takeObject({position={10+n,1,10},smooth=false});E.run(.1)
    expect("actual draw is "..g,c.getGUID()==g and TT.decode(c.getGMNotes()).id==g)
    expect("drawn card image is original "..g,c.getData().CustomDeck["1"].FaceURL=="https://example.test/"..g..".jpg")
  end
  local last=E.G.getObjectFromGUID("a00002")
  expect("last remaining card preserved as card",last~=nil and last.type=="Card" and TT.decode(last.getGMNotes()).id=="a00002")
  expect("single card order operations harmless",not TT.reorderEncounterTop(3,function() return 0 end) and not TT.moveTopEncounterBottom())
  expect("order caused no emulator errors",#E.errors==0)
end)

case("mulligan conservation and set-aside exclusions",function()
  local R,P,FX,AI,T,st,new=fixture();R.shuffle=function(x) return x end
  R.CARDS.sthrelias={name="Elias",wil=3,int=3,com=4,agi=2,health=8,sanity=8}
  local cards={};for n=1,30 do cards[n]={name="plain "..n} end
  cards[30]={name="Machete",type="Asset",slot="Hand",cost=3}
  cards[#cards+1]={name="Higher Education (3)",permanent=true}
  local sig,sigweak={name="signature"},{name="sigweak",weakness=true}
  local basic={name="Paranoia",weakness=true}
  local i=P.newInvestigator(1,"sthrelias","White",{},nil,nil,{cards=cards,signatures={sig,sigweak}},basic)
  expect("mulligan retains 30 plus two signatures and basic",#i.hand==5 and #i.deck==28)
  expect("role mulligan keeps useful weapon",i.hand[1].name=="Machete")
  local hand,deck={},{};for _,c in ipairs(i.hand) do hand[c.name]=(hand[c.name] or 0)+1 end;for _,c in ipairs(i.deck) do deck[c.name]=(deck[c.name] or 0)+1 end
  expect("rejected cards cannot be replacements",not hand.signature and not hand["plain 29"] and not hand["plain 28"] and not hand["plain 27"])
  expect("weaknesses set aside without resolving",not hand.sigweak and not hand.Paranoia and deck.sigweak==1 and deck.Paranoia==1 and R.G.metrics.weaknesses_drawn==0)
  expect("ordinary mulligan conserves all card identities",deck.signature==1 and deck["plain 29"]==1 and hand["plain 26"]==1 and hand["plain 23"]==1)
  expect("mulligan never draws permanent or changes resources",not hand["Higher Education (3)"] and not deck["Higher Education (3)"] and #i.assets==1 and i.resources==5)
end)
case("permanent basic weakness setup",function()
  local R,P,FX,AI,T,st,new=fixture();R.shuffle=function(x) return x end
  R.CARDS.fixture={name="fixture",wil=3,int=3,com=3,agi=3,health=8,sanity=8}
  local cards={};for n=1,30 do cards[n]={name="ordinary "..n} end
  local w={name="Indebted",weakness=true,permanent=true}
  local i=P.newInvestigator(1,"fixture","White",{},nil,nil,{cards=cards,signatures={}},w)
  local outside=true;for _,c in ipairs(i.hand) do if c==w then outside=false end end;for _,c in ipairs(i.deck) do if c==w then outside=false end end
  expect("Indebted permanent stays out of draw pile",outside and #i.hand==5 and #i.deck==25)
  expect("Indebted begins with three resources",i.resources==3)
end)

case("canceled symbols suppress weapon and event punishment",function()
  local R,P,FX,AI,T,st,new=fixture();local i=new("fixture");R.G.turnOf=i
  R.AI.prepareTest=function() return {},0 end
  P.cancelToken=function() return true end
  FX.tokenValue=function() return -2 end
  T.drawToken=function() return "Skull",nil end
  local ok,margin,token=R.test(i,"wil",3,{})
  expect("cancelled revealed token is neutral and marked",ok and margin==0 and token=="Canceled")
  local enemy={id="enemy",loc="x",engaged=i,def={evade=3,fight=3},damage=0};R.G.enemies={enemy}
  local horror=0;R.hurt=function(_,_,h) horror=horror+h end
  R.ACT.fight(i,enemy,{name="Shrivelling",uses=3})
  expect("canceled Shrivelling symbol inflicts no horror",horror==0 and enemy.damage==2)
  enemy.damage=0;i.actionsLeft=2
  local card={name="Blinding Light",level=2,cost=0,type="Event"};i.hand={card}
  R.ACT.play(i,card)
  expect("canceled Blinding symbol inflicts no punishment",horror==0 and i.actionsLeft==2 and enemy.damage==2)
end)
-- Finale eligibility comes from guide622/662: took part at the start, including
-- a participant defeated later; ending Years include pending Years. These
-- cases execute the actual setup and resolution functions without copying them.
local function endingFixture()
  local R,P,FX,AI,T,st,new=fixture()
  dofile("tools/play_engine/lua/finale.lua")(R,T)
  st.hour,st.stage=5,3
  R.G.logFlags,R.G.studyVisited={},{}
  R.G.contest=0
  T.cardWithId=function() return nil end
  T.placeBox=function() return {} end
  T.takeCard=function() return nil end
  local lead,other,prior=new("lead"),new("other"),new("prior")
  for _,i in ipairs(R.G.inv) do i.years,i.pendingYears,i.bracket=0,0,"Prime" end
  prior.defeated=true
  return R,P,T,st,lead,other,prior
end
case("finale participation survives later defeat",function()
  local R,P,T,st,lead,other,prior=endingFixture()
  lead.years,lead.bracket=15,"Ancient"
  R.beginFinale(other,false)
  lead.defeated=true
  R.G.contest=R.consts().contest
  expect("defeated finale participant still eligible",R.finaleResolution()=="R1")
  expect("participation capture excludes pre-finale defeat",R.G.finaleParticipants.lead and R.G.finaleParticipants.other and not R.G.finaleParticipants.prior)
  R.beginFinale(other,false)
  expect("repeated begin cannot replace participant record",R.G.finaleParticipants.lead)
end)
case("pre-finale defeat does not qualify",function()
  local R,P,T,st,lead,other,prior=endingFixture()
  prior.years,prior.bracket=15,"Ancient"
  R.beginFinale(lead,false);R.G.contest=R.consts().contest
  expect("absent Ancient does not supply ending condition",R.finaleResolution()=="R4")
end)
for _,v in ipairs({{14,0,"Elder","R4"},{14,1,"Elder","R1"},{10,4,"Elder","R4"},
  {10,5,"Elder","R1"},{15,0,"Prime","R1"},{0,0,"Ancient","R4"}}) do
  case("recorded plus pending ending threshold "..v[1].."+"..v[2],function()
    local R,P,T,st,lead,other,prior=endingFixture()
    lead.years,lead.pendingYears,lead.bracket=v[1],v[2],v[3]
    R.beginFinale(lead,false);R.G.contest=R.consts().contest
    expect("recorded plus pending classification "..v[1].."+"..v[2],R.finaleResolution()==v[4])
    expect("classification preserves recorded/pending/stat bracket "..v[1].."+"..v[2],lead.years==v[1] and lead.pendingYears==v[2] and lead.bracket==v[3])
  end)
end
case("pending Years gained during finale count after defeat",function()
  local R,P,T,st,lead,other,prior=endingFixture()
  lead.years,lead.bracket=14,"Elder"
  R.beginFinale(lead,false)
  R.pendingYear(lead,1,"independent ending probe")
  lead.defeated=true;R.G.contest=R.consts().contest
  expect("new pending Year and subsequent defeat retain eligibility",R.finaleResolution()=="R1")
  expect("pending Year does not prematurely age the stat line",lead.years==14 and lead.pendingYears==1 and lead.bracket=="Elder")
end)
case("legacy isolated ending fixture fallback",function()
  local R,P,T,st,lead=endingFixture()
  lead.years=nil;lead.bracket="Ancient"
  R.beginFinale(lead,false);R.G.contest=R.consts().contest
  expect("absent recorded Years retains legacy bracket fallback",R.finaleResolution()=="R1")
end)
case("ending priority chooses a guide-eligible result",function()
  local R,P,T,st,lead=endingFixture();lead.years=15
  R.beginFinale(lead,false);R.G.contest=R.consts().contest
  R.G.knowledge["the-vote-that-never-ends"]=true;R.G.knowledge["the-appointeds-name"]=true
  R.G.logFlags["The vote still stands"]=true
  expect("declared policy selects eligible Vote ending",R.finaleResolution()=="R2")
  R.G.knowledge["the-ticket-takers-bargain"]=true;R.G.logFlags["You hold the ticket"]=true
  st.memory=12
  expect("declared policy selects eligible ticket ending",R.finaleResolution()=="R1b")
  R.G.knowledge["the-keepers-ninth-death"]=true
  expect("declared policy selects eligible Keeper ending",R.finaleResolution()=="R3")
end)

-- Capture the actual private finish closure from the production engine's
-- zero-job bootstrap. All production modules are loaded; only the table API is
-- stubbed. debug.getlocal is test-only, and no model source is copied or edited.
local function finishFixture()
  local state={memory=8,loop=2,years={lead=14,other=3},pending={lead=1,other=0},oncard={lead=2,other=3}}
  local calls={}
  local function record(name,p) calls[#calls+1]={name=name,p=p} end
  local function copy(t) if type(t)~="table" then return t end;local o={};for k,v in pairs(t) do o[k]=copy(v) end;return o end
  local J={decode=function(v) return v end,encode=function(v) return v end}
  local E={J=J,run=function() end,spawnData=function() return {} end,drop=function() end,errors={}}
  local cfg={cards="probe-cards",decks="probe-decks",party={"lead","other"},jobs={},campaign=true}
  local files={config=cfg,["probe-cards"]={cards={},scenario_ids={}},["probe-decks"]={},payload={ObjectStates={{}}}}
  local T={E=E,J=J,MATS={"White","Blue"},errors={},init=function() end,decode=J.decode,
    click=function() end,difficulty=function() end,setInvestigators=function() end,
    mat=function() return {positionToWorld=function() return {x=0,y=0,z=0} end} end,
    find=function() return {getObjects=function() return {{guid="lead",gm_notes={id="lead"}},{guid="other",gm_notes={id="other"}}} end,takeObject=function() return {} end} end,
    st=function() return {memory=state.memory,band="Calm"} end,
    alive=function() return true end}
  T.ctl=function(name)
    record(name)
    if name=="Reset Loop" then state.loop=state.loop+1
    elseif name=="Memory" then state.memory=state.memory+1 end
  end
  T.tickLog=function(name,value)
    record("log:"..name,value)
    if name:sub(1,2)=="v:" then state.memory=state.memory+1 end
  end
  T.api=function(name,p)
    record(name,p)
    if name=="shApiSnapshot" then return {campaign={bankedMemory=state.memory,loopsCompleted=state.loop,years=copy(state.years),pendingYears=copy(state.pending),onCardMemory=copy(state.oncard)}} end
    if name=="shApiAge" then
      local gained=p.defeated and 3 or 2
      state.years[p.id]=state.years[p.id]+gained;state.pending[p.id]=0
      return {gained=gained}
    end
    if name=="shApiBankOnCard" then
      local banked=0;for id,v in pairs(state.oncard) do banked=banked+v;state.oncard[id]=0 end
      state.memory=state.memory+banked;return banked
    end
  end
  local captured,finish
  local oldDofile,oldWrite,oldFlush=dofile,io.write,io.flush
  local H={E=E,args={["suite-file"]="tools/play_engine/lua/engine.lua",config="config"},ROOT=".",payload="payload",
    readFile=function(path) return assert(files[path],path) end,info=function() end,
    check=function()
      local k=1
      while true do
        local name,value=debug.getlocal(2,k)
        if not name then break end
        if name=="finish" then finish=value end
        k=k+1
      end
    end}
  _G.dofile=function(path)
    if path:match("/tablekit%.lua$") then return T end
    local mod=oldDofile(path)
    if path:match("/rules%.lua$") then return function(R,t) captured=R;return mod(R,t) end end
    return mod
  end
  io.write,io.flush=function() end,function() end
  local ok,err=pcall(oldDofile("tools/play_engine/lua/engine.lua"),H)
  _G.dofile,io.write,io.flush=oldDofile,oldWrite,oldFlush
  assert(ok,err);assert(type(finish)=="function","actual engine finish closure not found")
  calls={}
  local lead={id="lead",years=14,pendingYears=1,bracket="Elder",memory=2}
  local other={id="other",years=3,pendingYears=0,bracket="Prime",memory=3,defeated=true}
  local G={name="independent accounting",seed=1,n=2,round=8,cfg={boxes={}},locList={},actOrder={},acts={},knowledge={},logFlags={},
    inv={lead,other},finaleParticipants={lead=true,other=true},contest=6,
    ended={reason="contest",round=8,hour=7,dissonance=4},trace={},
    metrics={victory={},start={memory=8},defeated={other=true},stage_max=3,acts_completed={},knowledge={},card_years=1}}
  captured.G=G
  local function count(name) local n=0;for _,v in ipairs(calls) do if v.name==name then n=n+1 end end;return n end
  return finish,captured,T,state,G,calls,count
end
for _,target in ipairs({"R1","R1b","R2","R3","R4","R5","R6"}) do
  case("finale finish stopping boundary "..target,function()
    local finish,R,T,state,G,calls,count=finishFixture()
    G.finale=true
    if target=="R1b" then
      G.knowledge["the-ticket-takers-bargain"]=true;G.logFlags["You hold the ticket"]=true
    elseif target=="R2" then
      G.knowledge["the-vote-that-never-ends"]=true;G.knowledge["the-appointeds-name"]=true;G.logFlags["The vote still stands"]=true
    elseif target=="R3" then G.knowledge["the-keepers-ninth-death"]=true
    elseif target=="R4" then G.inv[1].pendingYears=0;state.pending.lead=0
    elseif target=="R5" or target=="R6" then G.contest=0 end
    if target=="R6" then state.memory=7 end
    local before=state.memory
    local out=finish(G)
    expect(target.." is eligible actual ending classification",out.resolution==target)
    expect(target.." never calls Reset Loop",count("Reset Loop")==0 and state.loop==2)
    expect(target.." never opens/closes interlude, ages or banks",count("shApiInterlude")==0 and count("shApiAge")==0 and count("shApiBankOnCard")==0)
    expect(target.." preserves bank and on-card Memory",state.memory==before and state.oncard.lead==2 and state.oncard.other==3 and out.memory_on_cards==5 and out.memory_bank_end==before and out.memory_banked_on_cards==0)
    expect(target.." preserves recorded and pending Years",state.years.lead==14 and state.years.other==3 and state.pending.lead==(target=="R4" and 0 or 1) and G.inv[1].years==14 and G.inv[1].pendingYears==(target=="R4" and 0 or 1) and next(out.years)==nil)
    expect(target.." output explicitly excludes completed aftermath",out.finale_aftermath=="not simulated; resolve the ending and epilogue in the guide" and out.campaign_state.campaign.loopsCompleted==2)
    expect(target.." approximation declares ending choices and epilogues outside model",R.P.APPROX["Finale aftermath"]:find("ending choices and epilogues are not simulated",1,true)~=nil)
  end)
end
case("finale finish still claims Victory before classifying",function()
  local finish,R,T,state,G,calls,count=finishFixture()
  G.finale=true;G.contest=0;state.memory=7
  G.locList={{id="victory-probe",def={victory=1},revealed=true,closed=false,obj={}}}
  R.clues=function() return 0 end
  local out=finish(G)
  expect("legitimate Victory is claimed before finale affordability",out.resolution=="R5" and state.memory==8 and count("log:v:victory-probe")==1 and #out.metrics.victory==1)
  expect("Victory does not authorize ordinary finale aftermath",count("Reset Loop")==0 and count("shApiAge")==0 and count("shApiBankOnCard")==0)
end)
case("ordinary loop finish preserves interlude order",function()
  local finish,R,T,state,G,calls,count=finishFixture()
  G.ended.reason="reset"
  local out=finish(G)
  local names={};for _,v in ipairs(calls) do if v.name~="shApiSnapshot" then names[#names+1]=v.name end end
  expect("ordinary loop resets, opens, ages each, banks then closes",table.concat(names,"|")=="Reset Loop|shApiInterlude|shApiAge|shApiAge|shApiBankOnCard|shApiInterlude")
  expect("ordinary interlude open and close arguments preserved",calls[2].p.open==true and calls[6].p.open==false)
  expect("ordinary aging preserves defeated classification",calls[3].p.id=="lead" and calls[3].p.defeated==false and calls[4].p.id=="other" and calls[4].p.defeated==true and out.years.lead==2 and out.years.other==3)
  expect("ordinary loop banks the actual API result",state.loop==3 and state.memory==13 and out.memory_bank_end==13 and out.memory_on_cards==5 and out.memory_banked_on_cards==5)
  expect("ordinary result makes no finale aftermath claim",out.resolution=="R2" and out.finale_aftermath==nil)
end)
for _,ending in ipairs({"act","reset","defeat"}) do
  case("Prologue finish progression "..ending,function()
    local finish,R,T,state,G,calls,count=finishFixture()
    G.prologue=true;G.ended.reason=ending
    local out=finish(G)
    local expected=ending=="act" and "R1" or ending=="defeat" and "NR" or "R2"
    local award=4+(expected=="R1" and 1 or 0)
    expect("Prologue "..ending.." retains resolution and Memory reward",out.resolution==expected and count("Memory")==award and out.memory_bank_end==8+award+5)
    expect("Prologue "..ending.." records Unstuck and reset",count("log:k:you-are-unstuck")==1 and count("Reset Loop")==1 and state.loop==3)
    expect("Prologue "..ending.." avoids reset aging and open interlude",count("shApiAge")==0 and count("shApiInterlude")==1 and calls[#calls-1].p.open==false and next(out.years)==nil)
    expect("Prologue "..ending.." preserves banking and no finale claim",count("shApiBankOnCard")==1 and out.memory_banked_on_cards==5 and out.finale_aftermath==nil)
  end)
end

print(string.format("FINAL THIRD PASS: %d passed, %d failed",passed,failed))
if failed>0 then os.exit(1) end
