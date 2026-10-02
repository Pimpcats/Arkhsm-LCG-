-- SPOILERS: independent Rules Reference objective-window regression.
-- WITHDRAWN: the former expectation of paid advancement before Mythos encounters
-- was illegal. These expectations follow primary FFG RR pp3,23-26:
-- https://images-cdn.fantasyflightgames.com/filer_public/c4/b0/c4b0d66c-d79e-411b-bdb5-b5d8c457d4bc/ahc01_rules_reference_web.pdf
-- Optional clue spending uses actual player windows. No-cost mandatory delivery
-- and printed reactions retain their separate timing.
-- Standalone: no dependency on an earlier reviewer fixture or generated deck.
-- Loads effective cards and production rules/effects/players/flow/finale.
-- Lua 5.2 and 5.4 compatible.
local J=dofile('tests/tts_fake/json.lua')
local f=assert(io.open('campaigns/still_hour/card_overrides.json','r'))
local OV=J.decode(f:read('*a'));f:close()
-- Scenario probes use the current effective opening cost throughout; the
-- synthetic nested ability below separately declares its own one-clue cost.
local FIRST_COST=assert(tonumber(OV['sthr-act-firsthour'].clues))
local passed,failed=0,0
local function expect(label,ok)
  if ok then passed=passed+1;print('PASS '..label)
  else failed=failed+1;print('FAIL '..label) end
end
local function case(label,fn)
  local ok,err=pcall(fn)
  if not ok then failed=failed+1;print('ERROR '..label..': '..tostring(err)) end
end
local function resolve(fn)
  local ok,err=pcall(fn)
  if not ok and not (type(err)=='table' and err.loopEnded) then error(err,0) end
end
local function fixture(n,h)
  n=n or 1
  local st={hour=h or 7,dissonance=0,stage=0,band='Calm',memory=0}
  local events,draws={},0
  local ctx={events=events,tokens=0,prepares=0,available={},encounters={}}
  local G={cfg={},n=n,round=2,clock=0,phase='mythos',prologue=true,knowledge={},
    inv={},enemies={},appointed={},locs={},locList={},acts={},actOrder={'Prologue'},doom=1,
    inkRuns={},tempStatic={},group={},roundGroup={},crossedThisRound={},abilities={},
    metrics={doom_sources={},hour_sources={},dissonance_sources={},last_diss=0,diss_max=0,
      rewinds=0,cancelled_advances=0,acts_completed={},clues_spent=0,hour_round={},curve={},
      draw_failures=0,reshuffles=0,encounters=0,drawn={},tests=0,tests_passed=0,tokens={},
      damage=0,horror=0,damage_by={},horror_by={},clues=0,clues_by_round={},evades=0,
      knowledge={},actions={},enemy_moves=0,appointed_hunts=0,memory_on_cards={}}}
  local R={G=G,CARDS={}}
  for id,card in pairs(OV) do R.CARDS[id]=card end
  local E={run=function() end,rand=function() return 0 end}
  local T={E=E,st=function() return st end,ctl=function(name,right)
    if name=='Hour' then st.hour=st.hour+(right and -1 or 1)
    elseif name=='Appointed' then st.stage=st.stage+(right and -1 or 1) end
  end,dissonance=function(x) st.dissonance=st.dissonance+x end,
    cardWithId=function() return nil end,takeCard=function() return nil end,
    drawEncounter=function()
      draws=draws+1;events[#events+1]='draw:'..draws
      if ctx.onDraw then ctx.onDraw(draws) end
      return ctx.encounters[draws],false
    end,
    drawToken=function() ctx.tokens=ctx.tokens+1;events[#events+1]='token';return '0',{} end,
    returnTokens=function() events[#events+1]='returned token' end,
    cluesOn=function() return ctx.available end,
    moveClueToMat=function(token)
      for j,x in ipairs(ctx.available) do if x==token then table.remove(ctx.available,j);break end end
    end,
    gm=function(card) return {id=card.id} end,
    alive=function(obj) return obj~=nil and not obj.destroyed end,
    discardEncounter=function(card) card.discarded=true end,
    note=function() end,tickLog=function() end,api=function() end}
  dofile('tools/play_engine/lua/rules.lua')(R,T)
  local FX=dofile('tools/play_engine/lua/effects.lua')(R,T)
  local P=dofile('tools/play_engine/lua/players.lua')(R,T)
  dofile('tools/play_engine/lua/flow.lua')(R,T)
  dofile('tools/play_engine/lua/finale.lua')(R,T)
  local function addLocation(guid,id)
    local L={id=id,guid=guid,name=id,revealed=true,closed=false,def=OV[id] or {},adj={},
      obj={getPosition=function() return {x=0,y=1,z=0} end}}
    G.locs[guid]=L;G.locList[#G.locList+1]=L;return L
  end
  ctx.addLocation=addLocation
  local steps=addLocation('steps','sthr-loc-almanacsteps')
  for j=1,n do
    G.inv[j]={id='fixture'..j,name='fixture'..j,loc='steps',clues=FIRST_COST,clueTokens={},
      assets={},hand={},deck={},discard={},threat={},round={},loopUsed={},lastTurn={},testedTypes={},failedTypes={},
      memory=0,cardMemory=0,damage=2,horror=2,health=8,sanity=8,color='White',
      resources=5,actionsLeft=3,stats={int=4,wil=4,com=4,agi=4}}
  end
  G.acts.Prologue={id='sthr-act-firsthour',district='Prologue',completed=false}
  ctx.act=G.acts.Prologue
  R.locOf=function(i) return i and G.locs[i.loc] end
  R.locById=function(id) for _,L in pairs(G.locs) do if L.id==id then return L end end end
  R.investigatorsAt=function(L)
    local list={};for _,i in ipairs(G.inv) do if L and i.loc==L.guid and not i.defeated then list[#list+1]=i end end;return list
  end
  R.moveHourCard=function() end;R.returnHourCard=function() end
  R.scanLocationsLight=function() end;R.scanLocations=function() end
  R.syncAppointedArrival=function() end
  R.hourPrevent=function() return nil end
  R.placeEnemy=function() end;R.engageAt=function() end;R.appointedLoc=function() return nil end
  R.shroud=function() return 1 end
  R.AI={wantsAdvance=function() return true end,turnOrder=function() return G.inv end,
    startTurn=function() events[#events+1]='turn began' end,choose=function() return nil end,
    prepareTest=function(inv,skill,diff,base,opts)
      ctx.prepares=ctx.prepares+1;events[#events+1]='commits'
      if ctx.onPrepare then return ctx.onPrepare(inv,skill,diff,base,opts) end
      return {},0
    end}
  FX.checkWakes=function() end -- unrelated location/enemy wake rules
  local realReached=FX.onHourReached
  FX.onHourReached=function(hour,cancelled)
    events[#events+1]='reached:'..hour
    realReached(hour,cancelled)
  end
  local realAfter=FX.afterAdvance
  FX.afterAdvance=function()
    events[#events+1]='after:'..st.hour
    realAfter()
  end
  local realAdvance=R.advanceAct
  R.advanceAct=function(act,by)
    events[#events+1]='advance:'..act.id;return realAdvance(act,by)
  end
  local realWindow=R.playerWindow
  R.playerWindow=function(why)
    events[#events+1]='window:'..tostring(why)
    return assert(realWindow,'production R.playerWindow required')(why)
  end
  ctx.queueTest=function()
    local card={id='fixture-test',getName=function() return 'fixture encounter test' end}
    R.CARDS[card.id]={type='Treachery',text=''}
    FX.ENC[card.id]=function(inv)
      events[#events+1]='revelation';R.test(inv,'wil',1,{kind='treachery'})
      events[#events+1]='revelation resolved';return 'discard'
    end
    ctx.encounters[1]=card;return card
  end
  ctx.draws=function() return draws end
  return R,P,FX,T,st,ctx,steps
end
local function count(events,prefix)
  local n=0;for _,e in ipairs(events) do if e:sub(1,#prefix)==prefix then n=n+1 end end;return n
end
local function join(events) return table.concat(events,',') end

local function index(events,value)
  for j,e in ipairs(events) do if e==value then return j end end
end
local function before(events,a,b)
  local j,k=index(events,a),index(events,b);return j~=nil and k~=nil and j<k
end

expect('current opening metadata is two clues per investigator',
  FIRST_COST==2 and OV['sthr-act-firsthour'].clues_per_investigator==true)
expect('current printed opening cost matches metadata and plural wording',
  OV['sthr-act-firsthour'].text:find('spend '..FIRST_COST..' [perinv] clues to advance.',1,true)~=nil)
for n=1,4 do
  case('Mythos ordinary paid objective '..n,function()
    local R,P,FX,T,st,C=fixture(n,7);local unpaid=true
    C.onDraw=function() unpaid=unpaid and not C.act.completed and R.G.metrics.clues_spent==0 end
    resolve(function() R.mythos() end)
    expect('count '..n..' doom precedes normal encounters',before(C.events,'reached:8','draw:1'))
    expect('count '..n..' no payment before or between non-test encounters',unpaid and C.draws()==n)
    expect('count '..n..' payment follows complete encounter step',before(C.events,'draw:'..n,'advance:sthr-act-firsthour'))
    expect('count '..n..' legal window pays printed full cost',R.G.ended and R.G.ended.reason=='act' and R.G.metrics.clues_spent==n*FIRST_COST and st.hour==8)
  end)
  case('one-short opening payment '..n,function()
    local R,P,FX,T,st,C=fixture(n,8);R.G.inv[n].clues=FIRST_COST-1
    R.playerWindow('fixture actual-cost one-short')
    expect('count '..n..' one-short payment rejects without mutation',
      not C.act.completed and not R.G.ended and R.G.metrics.clues_spent==0 and R.partyClues()==n*FIRST_COST-1)
  end)
end
case('no paid advance at Mythos beginning',function()
  local R,P,FX,T,st,C=fixture(1,8);R.G.doom=0
  C.onDraw=function() R.advance(1,'encounter terminal advance') end
  resolve(function() R.mythos() end)
  expect('already eligible act cannot bypass encounters at phase start',C.draws()==1 and R.G.ended and R.G.ended.reason=='hour9')
  expect('terminal encounter spends no act clues',not C.act.completed and R.G.metrics.clues_spent==0)
end)
case('legal ST.1 window during encounter resolution',function()
  local R,P,FX,T,st,C=fixture(3,7);C.queueTest()
  resolve(function() R.mythos() end)
  expect('encounter test window precedes remaining investigator draws',C.draws()==1 and R.G.ended and R.G.ended.reason=='act')
  expect('ST.1 window follows encounter revelation initiation',before(C.events,'revelation','advance:sthr-act-firsthour'))
  expect('ST.1 payment precedes commits and token reveal',C.prepares==0 and C.tokens==0)
  expect('ST.1 payment still pays complete cost',R.G.metrics.clues_spent==3*FIRST_COST)
end)
case('legal ST.2 window after commits',function()
  local R,P,FX,T,st,C=fixture(1,7);R.G.inv[1].clues=0;C.queueTest()
  C.onPrepare=function(inv) inv.clues=FIRST_COST;return {},0 end
  resolve(function() R.mythos() end)
  expect('post-commit window sees changed eligibility',C.prepares==1 and C.act.completed and R.G.metrics.clues_spent==FIRST_COST)
  expect('ST.2 payment follows commits and precedes token',before(C.events,'commits','advance:sthr-act-firsthour') and C.tokens==0)
  expect('ST.2 resolution ends before remaining revelation effects',index(C.events,'revelation resolved')==nil)
end)
case('ineligible encounter test resolves normally',function()
  local R,P,FX,T,st,C=fixture(2,7);R.G.inv[1].clues=0;R.G.inv[2].clues=0;C.queueTest()
  resolve(function() R.mythos() end)
  expect('normal test keeps both pre-token windows',count(C.events,'window:skill test')==2 and C.prepares==1 and C.tokens==1)
  expect('ineligible test cannot pay or prevent remaining encounters',not R.G.ended and C.draws()==2 and R.G.metrics.clues_spent==0)
  expect('full revelation precedes next investigator draw',before(C.events,'revelation resolved','draw:2'))
end)
case('automatic-only default and explicit player window',function()
  local R,P,FX,T,st,C=fixture(1,8)
  R.checkObjectives();R.checkObjectives(false)
  expect('default and explicit false do not pay a free act ability',not C.act.completed and R.G.inv[1].clues==FIRST_COST and R.G.metrics.clues_spent==0)
  resolve(function() R.playerWindow('fixture legal window') end)
  expect('production playerWindow permits optional printed payment',C.act.completed and R.G.metrics.clues_spent==FIRST_COST and R.G.ended.reason=='act')
end)
case('nested consequences do not inherit paid permission',function()
  local R,P,FX,T,st,C,L=fixture(1,8);local inv=R.G.inv[1];inv.clues=1
  -- A synthetic paid ability isolates the timing contract: its consequence
  -- discovers a clue, then continues resolving before the next player window.
  R.CARDS['fixture-paid-ability']={clues=1}
  FX.ACTS['fixture-paid-ability']={at='sthr-loc-almanacsteps',contrib=true}
  local auxiliary={id='fixture-paid-ability'}
  R.G.acts.Auxiliary=auxiliary;R.G.actOrder={'Auxiliary'}
  for j=1,FIRST_COST do C.available[j]={destruct=function() end} end
  local realAdvance=R.advanceAct
  R.advanceAct=function(act,by)
    if act~=auxiliary then return realAdvance(act,by) end
    act.completed=true;R.G.actOrder={'Prologue'}
    R.discover(inv,L,FIRST_COST)
    C.events[#C.events+1]='nested consequence complete'
    R.G.actOrder={'Auxiliary'}
  end
  resolve(function() R.playerWindow('auxiliary ability window') end)
  expect('default check within paid consequence cannot pay nested objective',auxiliary.completed and not C.act.completed and not R.G.ended and inv.clues==FIRST_COST)
  expect('nested consequence finishes without prematurely consuming new clue',index(C.events,'nested consequence complete')~=nil and R.G.metrics.clues_spent==1)
  R.G.actOrder={'Prologue'}
  resolve(function() R.playerWindow('following legal ability window') end)
  expect('new optional ability may be triggered in following window',C.act.completed and R.G.metrics.clues_spent==1+FIRST_COST)
end)
case('paid advancement remains optional',function()
  local R,P,FX,T,st,C=fixture(1,8);R.AI.wantsAdvance=function() return false end
  R.playerWindow('fixture declined payment')
  expect('AI may decline optional clue payment',not C.act.completed and R.G.inv[1].clues==FIRST_COST and R.G.metrics.clues_spent==0)
end)
case('full affordability and eligible contributors in legal windows',function()
  local R,P,FX,T,st,C,L=fixture(3,8);R.G.inv[3].clues=FIRST_COST-1
  R.playerWindow('fixture one-short')
  expect('one-short legal window cannot partially pay',not C.act.completed and R.G.metrics.clues_spent==0 and R.G.inv[1].clues==FIRST_COST)
  R.G.inv[3].clues=FIRST_COST;R.G.inv[3].loc='elsewhere';R.playerWindow('fixture remote payer')
  expect('remote clues cannot meet local contribution',not C.act.completed and R.G.metrics.clues_spent==0)
  R.G.inv[3].loc='steps';L.closed=true;R.playerWindow('fixture closed')
  expect('closed location unavailable even in a legal window',not C.act.completed and R.G.metrics.clues_spent==0)
end)
case('complete investigate consequences before paid advancement',function()
  local R,P,FX,T,st,C=fixture(1,8);local inv=R.G.inv[1];inv.clues=FIRST_COST-1
  inv.assets={{name='Dr. Milan Christopher'}}
  local deduction={name='Deduction',level=0}
  C.onPrepare=function() return {{owner=inv,card=deduction,icons=1}},0 end
  for j=1,2 do C.available[j]={destruct=function() end} end
  resolve(function() R.ACT.investigate(inv) end)
  expect('discover does not pay when first clue becomes sufficient',not C.act.completed and not R.G.ended and R.G.metrics.clues_spent==0)
  expect('complete Deduction two-clue result resolves',inv.clues==FIRST_COST+1 and R.G.metrics.clues==2 and #C.available==0)
  expect('remaining asset effect and committed card resolve',inv.resources==6 and inv.discard[1]==deduction)
  resolve(function() R.playerWindow('after complete investigate action') end)
  expect('following window pays after complete action',C.act.completed and R.G.metrics.clues_spent==FIRST_COST and inv.clues==1)
end)
case('complete advance alone does not offer paid window',function()
  local R,P,FX,T,st,C=fixture(1,7);R.advance(1,'framework advance')
  expect('advance leaves optional payment pending at eight',st.hour==8 and not R.G.ended and not C.act.completed and R.G.metrics.clues_spent==0)
  expect('advance manufactures no player window',count(C.events,'window:')==0)
  resolve(function() R.playerWindow('next legal window') end)
  expect('next actual window permits payment',R.G.ended and R.G.ended.reason=='act')
end)
case('multi-Hour advance ending at eight',function()
  local R,P,FX,T,st,C=fixture(1,6);R.advance(2,'complete skip')
  expect('multi-Hour skip has no intermediate or final paid window',not R.G.ended and not C.act.completed and count(C.events,'window:')==0)
  expect('both reached effects precede complete after-advance',before(C.events,'reached:7','reached:8') and before(C.events,'reached:8','after:8'))
  expect('per-Hour healing remains complete',R.G.inv[1].damage==0 and R.G.inv[1].horror==0)
  resolve(function() R.playerWindow('next actual window') end)
  expect('multi-Hour skip pays at next legal window',R.G.ended and R.G.ended.reason=='act' and R.G.metrics.clues_spent==FIRST_COST)
end)
case('multi-Hour terminal suppression',function()
  local R,P,FX,T,st,C=fixture(1,7);resolve(function() R.advance(2,'terminal skip') end)
  expect('terminal skip reaches nine before optional payment',R.G.ended and R.G.ended.reason=='hour9' and st.hour==9 and not C.act.completed)
  expect('terminal skip consumes no clues or invented windows',R.G.metrics.clues_spent==0 and count(C.events,'window:')==0)
  expect('terminal reached text suppresses complete after-advance',index(C.events,'after:9')==nil)
end)
case('whole cancellation and canceled reached text',function()
  local R,P,FX,T,st,C=fixture(1,7);R.G.rememberEnding=R.G.round;R.G.doom=4
  R.advance(3,'canceled skip')
  expect('whole cancellation has no reached/delivery/window',st.hour==7 and #C.events==0 and not C.act.completed)
  expect('cancellation clears doom without payment/healing',R.G.doom==0 and R.G.metrics.clues_spent==0 and R.G.inv[1].damage==2 and R.G.inv[1].horror==2)
  R.hourPrevent=function(h) return h==8 end;R.advance(1,'canceled reached text')
  expect('canceled reached text completes advance without paid window',st.hour==8 and index(C.events,'after:8') and not C.act.completed and count(C.events,'window:')==0)
  resolve(function() R.playerWindow('next legal window') end)
  expect('canceled reached text permits later legal payment',C.act.completed and R.G.metrics.clues_spent==FIRST_COST)
end)
case('reset and forced after-advance consequences',function()
  local R,P,FX,T,st,C=fixture(1,7);local old=T.ctl
  T.ctl=function(name,right) old(name,right);if name=='Hour' then st.dissonance=R.consts().reset end end
  resolve(function() R.advance(1,'reset fixture') end)
  expect('reset suppresses complete after-advance and payment',R.G.ended and R.G.ended.reason=='reset' and not C.act.completed and index(C.events,'after:8')==nil)
  R,P,FX,T,st,C=fixture(1,7);FX.afterAdvance=function() R.G.inv[1].defeated=true end
  R.advance(1,'forced after-effect');R.playerWindow('later legal window')
  expect('forced defeat prevents later clue payment',not C.act.completed and R.G.metrics.clues_spent==0)
end)
case('rewind, zero, ended calls and absent act order',function()
  local R,P,FX,T,st,C=fixture(1,8)
  R.rewind(1,'rewind');R.advance(0,'zero');R.advance(-1,'negative')
  expect('rewind and nonpositive advances never pay',st.hour==7 and #C.events==0 and not C.act.completed)
  R.G.ended={reason='already'};R.advance(1,'ended');R.playerWindow('ended')
  expect('ended play cannot pay',st.hour==7 and not C.act.completed and R.G.metrics.clues_spent==0)
  R,P,FX,T,st,C=fixture(1,6);R.G.actOrder=nil;R.G.acts={}
  R.advance(1,'empty');R.playerWindow('empty')
  expect('isolated callers tolerate absent act order',st.hour==7 and not R.G.ended)
end)
case('mandatory carry delivery bypasses optional policy',function()
  local R,P,FX,T,st,C=fixture(1,5);local inv=R.G.inv[1]
  C.addLocation('vestry','sthr-loc-vestry');inv.loc='vestry';inv.clues=0
  local act={id='sthr-act-hourwaswrong',district='Church',holder=inv}
  inv.story={id='sthr-item-drownedpage',act=act}
  R.G.prologue=false;R.G.actOrder={'Church'};R.G.acts={Church=act}
  R.AI.wantsAdvance=function() return false end;R.checkObjectives()
  expect('mandatory arrival advances without window or AI approval',act.completed and inv.story==nil and R.G.knowledge['the-hour-was-wrong'])
  expect('purchased delivery charges no second clue payment',R.G.metrics.clues_spent==0 and count(C.events,'window:')==0)
end)
case('printed after-advance delivery exact timing',function()
  local R,P,FX,T,st,C=fixture(1,6);local inv=R.G.inv[1]
  C.addLocation('belfry','sthr-loc-belfry');inv.loc='belfry';inv.clues=0
  local act={id='sthr-act-whythirteen',district='Church',holder=inv}
  inv.story={id='sthr-item-register',act=act}
  R.G.prologue=false;R.G.actOrder={'Church'};R.G.acts={Church=act};R.AI.wantsAdvance=function() return false end
  R.checkObjectives();expect('arrival alone does not deliver Register',not act.completed)
  R.G.rememberEnding=R.G.round;R.advance(2,'canceled delivery')
  expect('canceled complete advance cannot deliver',not act.completed and st.hour==6)
  R.advance(2,'complete delivery skip')
  expect('delivery waits for complete multi-Hour advance',act.completed and before(C.events,'reached:8','advance:sthr-act-whythirteen'))
  expect('mandatory delivery needs no paid player window',count(C.events,'window:')==0 and R.G.metrics.clues_spent==0 and inv.story==nil)
end)
case('printed paid evade reaction retains timing',function()
  for _,full in ipairs({false,true}) do
    local R,P,FX,T,st,C=fixture(1,5);local inv=R.G.inv[1]
    C.addLocation('turning','sthr-loc-turning');inv.loc='turning';inv.clues=full and 4 or 3
    local act={id='sthr-act-walksbeside',district='Road'}
    R.G.prologue=false;R.G.actOrder={'Road'};R.G.acts={Road=act};R.G.walksBesideCurrent=true
    local en={id='fixture_echo',loc='turning',engaged=inv,damage=0,def={traits='Echo.',evade=1,fight=3,health=3}}
    R.G.enemies={en};R.ACT.evade(inv,en)
    expect('evade resolves before reaction full='..tostring(full),en.exhausted and en.engaged==nil and C.tokens==1)
    expect('reaction charges only full printed cost full='..tostring(full),(not not act.completed)==full and R.G.metrics.clues_spent==(full and 4 or 0))
    expect('reaction invents no post-test free window full='..tostring(full),count(C.events,'window:')==2)
    if full then expect('paid reaction follows resolved test',before(C.events,'returned token','advance:sthr-act-walksbeside')) end
  end
end)
case('Investigation window follows turn beginning',function()
  local R,P,FX,T,st,C=fixture(1,8);resolve(function() R.investigation() end)
  expect('no paid advance before next turn begins',before(C.events,'turn began','advance:sthr-act-firsthour'))
  expect('legal turn pre-action window can pay',C.act.completed and R.G.metrics.clues_spent==FIRST_COST)
end)
case('no window after turn-end/investigation-end consequences',function()
  local R,P,FX,T,st,C=fixture(1,8);R.G.inv[1].clues=0;local realEnd=P.endTurn
  P.endTurn=function(inv) realEnd(inv);inv.clues=FIRST_COST;C.events[#C.events+1]='turn ended consequence' end
  resolve(function() R.investigation() end)
  expect('turn-end affordability cannot use invented phase-end window',not C.act.completed and not R.G.ended and R.G.metrics.clues_spent==0)
  expect('complete turn-end consequence still resolves',index(C.events,'turn ended consequence')~=nil)
end)
case('Enemy window after complete Hunter step',function()
  local R,P,FX,T,st,C,steps=fixture(1,8);C.addLocation('away','fixture-away')
  for j=1,2 do R.G.enemies[j]={id='hunter'..j,name='hunter'..j,loc='away',def={}} end
  R.isHunter=function() return true end;R.sleepwalking=function() return false end
  R.AI.huntTarget=function() return steps end;R.route=function() return steps end
  R.placeEnemy=function(en) C.events[#C.events+1]='hunter moved:'..en.id end;FX.onEnemyMoved=function() end
  resolve(function() R.enemyPhase() end)
  expect('no paid window before all Hunters finish moving',R.G.enemies[1].loc=='steps' and R.G.enemies[2].loc=='steps')
  expect('legal post-Hunter window permits payment',before(C.events,'hunter moved:hunter2','advance:sthr-act-firsthour') and C.act.completed)
end)
case('Enemy windows between investigator batches',function()
  for _,terminalSecond in ipairs({false,true}) do
    local R,P,FX,T,st,C=fixture(2,8);for _,inv in ipairs(R.G.inv) do inv.clues=0 end
    R.sleepwalking=function() return false end;local one,two=R.G.inv[1],R.G.inv[2]
    R.G.enemies={{id='first',name='first',engaged=one,def={}},{id='second',name='second',engaged=one,def={}},{id='third',name='third',engaged=two,def={}}}
    local attacks=0
    R.enemyAttack=function(en,inv)
      attacks=attacks+1;C.events[#C.events+1]='attack:'..en.id
      if en.id=='first' then one.clues=2*FIRST_COST end
      if (terminalSecond and en.id=='second') or (not terminalSecond and en.id=='third') then R.advance(1,'attack terminal advance') end
    end
    resolve(function() R.enemyPhase() end)
    if terminalSecond then
      expect('no paid window within same investigator attack batch',attacks==2 and R.G.ended and R.G.ended.reason=='hour9' and not C.act.completed)
      expect('same-batch terminal effect preserves objective clues',one.clues==2*FIRST_COST and R.G.metrics.clues_spent==0)
    else
      expect('legal window follows first complete investigator batch',attacks==2 and C.act.completed and R.G.ended.reason=='act')
      expect('batch window precedes next investigator attacks',index(C.events,'attack:third')==nil and before(C.events,'attack:second','advance:sthr-act-firsthour'))
    end
  end
end)
case('Upkeep pre-ready legal window',function()
  local R,P,FX,T,st,C=fixture(1,8);local asset={name='fixture asset',exhausted=true};R.G.inv[1].assets={asset}
  P.draw=function() C.events[#C.events+1]='upkeep draw' end
  resolve(function() R.upkeep() end)
  expect('post-reset pre-ready window can pay before readying/drawing',C.act.completed and asset.exhausted and index(C.events,'upkeep draw')==nil)
end)
case('no Upkeep window between draws and end-round consequences',function()
  for _,defeated in ipairs({false,true}) do
    local R,P,FX,T,st,C=fixture(1,8);local inv=R.G.inv[1];inv.clues=0
    P.draw=function(i) i.clues=FIRST_COST;C.events[#C.events+1]='upkeep draw' end
    FX.endOfRound=function() C.events[#C.events+1]='end-round consequence';if defeated then inv.defeated=true end end
    resolve(function() R.upkeep() end)
    if defeated then
      expect('round-end defeat precedes a new paid window',inv.defeated and not C.act.completed and R.G.metrics.clues_spent==0)
    else
      expect('post-round payment follows all mandatory round-end effects',C.act.completed and before(C.events,'end-round consequence','advance:sthr-act-firsthour'))
      expect('ordinary Upkeep resource gain resolves before advance',inv.resources==6)
    end
  end
end)

print(string.format('INDEPENDENT OBJECTIVE WINDOWS RR: %d passed, %d failed',passed,failed))
if failed>0 then os.exit(1) end
