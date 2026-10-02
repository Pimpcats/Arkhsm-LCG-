-- SPOILERS: independent limited balance/cost verification; source read only.
-- Standalone: reads current override JSON directly and loads production rules.
local J=dofile('tests/tts_fake/json.lua')
local f=assert(io.open('campaigns/still_hour/card_overrides.json','r'))
local OV=J.decode(f:read('*a'));f:close()
local passed,failed=0,0
local function expect(label,ok)
  if ok then passed=passed+1;print('PASS '..label)
  else failed=failed+1;print('FAIL '..label) end
end
local function case(label,fn)
  local ok,e=pcall(fn);if not ok then failed=failed+1;print('ERROR '..label..': '..tostring(e)) end
end
local function fixture(n,id)
  local st={hour=5,dissonance=0,stage=0,band='Calm',memory=0}
  local returned,tests=0,0
  local district=id=='sthr-act-walksbeside' and 'Road' or 'Church'
  local R={CARDS=OV,G={n=n,round=1,clock=0,phase='investigation',cfg={objectives={id}},
    inv={},enemies={},appointed={},knowledge={},partTwo=true,acts={},actOrder={district},locs={},locList={},
    tempStatic={},group={},roundGroup={},crossedThisRound={},abilities={},
    metrics={tests=0,tests_passed=0,tokens={},damage=0,horror=0,damage_by={},horror_by={},
      clues_spent=0,evades=0,rewinds=0,cancelled_advances=0,doom_sources={},hour_sources={},
      dissonance_sources={},diss_max=0,memory_on_cards={}}}}
  local T={E={run=function() end,rand=function() return 0 end},st=function() return st end,
    ctl=function(name,right) if name=='Hour' then st.hour=st.hour+(right and -1 or 1) end end,
    spawnClueOn=function(_,n) returned=returned+n end}
  dofile('tools/play_engine/lua/rules.lua')(R,T)
  local FX=dofile('tools/play_engine/lua/effects.lua')(R,T)
  local P=dofile('tools/play_engine/lua/players.lua')(R,T)
  dofile('tools/play_engine/lua/flow.lua')(R,T)
  dofile('tools/play_engine/lua/finale.lua')(R,T)
  local AI=dofile('tools/play_engine/lua/ai.lua')(R,T)
  local locNames={vestry='sthr-loc-vestry',crypt='sthr-loc-floodedcrypt',belfry='sthr-loc-belfry',turning='sthr-loc-turning',hub='sthr-loc-hubsquare'}
  for guid,cid in pairs(locNames) do
    local L={guid=guid,id=cid,closed=false,revealed=true,def=OV[cid] or {},adj={},obj={getPosition=function() return {x=0,y=1,z=0} end}}
    R.G.locs[guid]=L;R.G.locList[#R.G.locList+1]=L
  end
  local pickup=id=='sthr-act-whythirteen' and 'vestry' or id=='sthr-act-hourwaswrong' and 'crypt' or 'turning'
  for j=1,n do
    R.G.inv[j]={id='fixture'..j,name='fixture'..j,idx=j,loc=pickup,clues=0,clueTokens={},
      assets={},hand={},deck={},discard={},threat={},round={},loopUsed={},lastTurn={},testedTypes={},failedTypes={},
      memory=0,cardMemory=0,damage=0,horror=0,health=8,sanity=8,resources=5,actionsLeft=3,stats={wil=4,com=3,int=3,agi=3}}
  end
  local act={id=id,district=district,completed=false};R.G.acts[district]=act
  R.locOf=function(i) return i and R.G.locs[i.loc] end
  R.locById=function(cid) for _,L in pairs(R.G.locs) do if L.id==cid then return L end end end
  R.investigatorsAt=function(L) local out={};for _,i in ipairs(R.G.inv) do if L and i.loc==L.guid and not i.defeated then out[#out+1]=i end end;return out end
  R.clues=function() return 0 end;R.shroud=function() return 1 end;R.prob=function() return 1 end
  R.route=function(from,to) if from==to then return nil,0,0 end return nil,99,0 end
  R.canEnter=function() return false end;R.isCrossing=function() return false end
  R.appointedLoc=function() return nil end
  R.placeEnemy=function() end;R.moveHourCard=function() end;R.returnHourCard=function() end
  R.syncAppointedArrival=function() end;R.scanLocationsLight=function() end
  FX.onHourReached=function() end;R.hourPrevent=function() return nil end
  FX.checkWakes=function() end
  -- Keep movement/clue-target policy irrelevant to the tested cost decision.
  -- AI.choose itself and its objective affordability gates remain production.
  AI.targetFor=function(i) return R.locOf(i),'go' end
  R.advanceAct=function(a,by) a.completed=true;a.by=by;if a.holder then a.holder.story=nil;a.holder=nil end end
  R.test=function() tests=tests+1;return true,1,'0' end
  return R,FX,AI,st,act,R.G.inv[1],function() return tests,returned end
end
for _,id in ipairs({'sthr-act-whythirteen','sthr-act-hourwaswrong','sthr-act-walksbeside'}) do
  local expected=id=='sthr-act-walksbeside' and 3 or (id=='sthr-act-hourwaswrong' and 2 or 3)
  expect(id..' effective metadata has intended per-investigator cost',OV[id].clues==expected and OV[id].clues_per_investigator)
  local count=0;for _ in OV[id].text:gmatch(expected..' %[%s*perinv%s*%] clues') do count=count+1 end
  expect(id..' printed payment routes match metadata',count==(id=='sthr-act-walksbeside' and 2 or 1))
end
for n=1,4 do
 for _,id in ipairs({'sthr-act-whythirteen','sthr-act-hourwaswrong'}) do
  local C=(id=='sthr-act-hourwaswrong') and 2 or 3
  case(id..' full cost '..n,function()
    local R,FX,AI,st,act,i=fixture(n,id)
    expect(id..' scaled cost '..n,FX.actNeed(id)==C*n)
    for _,x in ipairs(R.G.inv) do x.clues=C end
    local choice=AI.choose(i)
    expect(id..' AI selects one action only when fully paid '..n,choice and choice.kind=='objective' and choice.actions==1)
    expect(id..' direct payment succeeds '..n,R.takeStory(i,act)==true and R.G.metrics.clues_spent==C*n and act.holder==i and i.story~=nil)
    expect(id..' story already held owes no more '..n,FX.actNeed(id)==0)
  end)
  case(id..' insufficient cost '..n,function()
    local R,FX,AI,st,act,i=fixture(n,id)
    for _,x in ipairs(R.G.inv) do x.clues=C end;i.clues=C-1
    local choice=AI.choose(i)
    expect(id..' AI bars one-short payment '..n,not choice or choice.kind~='objective')
    expect(id..' direct one-short rejects without mutation '..n,R.takeStory(i,act)==false and i.clues==C-1 and R.G.metrics.clues_spent==0 and not i.story and not act.holder and not R.G.metrics.story_taken)
  end)
  case(id..' affordability race '..n,function()
    local R,FX,AI,st,act,i=fixture(n,id)
    for _,x in ipairs(R.G.inv) do x.clues=C end
    local choice=AI.choose(i);i.clues=i.clues-1
    if choice then choice.run() end
    expect(id..' AI-selected execution rechecks full cost '..n,choice and choice.kind=='objective' and not i.story and R.G.metrics.clues_spent==0 and i.clues==C-1)
  end)
 end
 for _,route in ipairs({'action','reaction'}) do
  for _,full in ipairs({false,true}) do
   case('Road '..route..' '..n..' full='..tostring(full),function()
    local R,FX,AI,st,act,i,counts=fixture(n,'sthr-act-walksbeside');R.G.walksBesideCurrent=true
    for _,x in ipairs(R.G.inv) do x.clues=3 end;if not full then i.clues=2 end
    local en={id='fixture_echo',name='echo',loc='turning',engaged=nil,exhausted=false,damage=0,def={traits='Echo.',fight=3,evade=3,health=3}};R.G.enemies={en}
    expect('Road action/reaction cost '..route..n..tostring(full),R.walksBesideCost()==3*n)
    if route=='action' then
      local choice=AI.choose(i)
      expect('Road AI full threshold '..n..tostring(full),full and choice and choice.kind=='objective' or not full and (not choice or choice.kind~='objective'))
      R.standFirm(i,en)
    else en.engaged=i;R.ACT.evade(i,en) end
    local tests=counts()
    expect('Road '..route..' exact affordability '..n..tostring(full),act.completed==full and R.G.metrics.clues_spent==(full and 3*n or 0))
    expect('Road '..route..' no partial clue loss '..n..tostring(full),i.clues==(full and 0 or 2))
    if route=='action' then expect('Road no unpaid test '..n..tostring(full),tests==(full and 1 or 0)) end
   end)
  end
 end
end
case('Church payer scope',function()
 local R,FX,AI,st,act,i=fixture(2,'sthr-act-whythirteen');i.clues=3;R.G.inv[2].clues=3;R.G.inv[2].loc='hub'
 expect('surface accepts remote group contribution',R.takeStory(i,act) and R.G.metrics.clues_spent==6)
 R,FX,AI,st,act,i=fixture(2,'sthr-act-hourwaswrong');i.clues=3;R.G.inv[2].clues=3;R.G.inv[2].loc='hub'
 local choice=AI.choose(i)
 expect('deep AI rejects remote-only affordability',not choice or choice.kind~='objective')
 expect('deep rejects remote contributors atomically',not R.takeStory(i,act) and i.clues==3 and R.G.inv[2].clues==3 and R.G.metrics.clues_spent==0)
end)
case('carry pickup legality and drop',function()
 local R,FX,AI,st,act,i=fixture(1,'sthr-act-whythirteen');i.clues=3;i.loc='hub'
 expect('wrong pickup rejected without spending',not R.takeStory(i,act) and i.clues==3 and not act.holder)
 i.loc='vestry';R.G.locs.vestry.closed=true
 expect('closed pickup rejected without spending',not R.takeStory(i,act) and i.clues==3 and not act.holder)
 R.G.locs.vestry.closed=false;i.defeated=true
 expect('eliminated actor rejected without spending',not R.takeStory(i,act) and i.clues==3 and not act.holder)
 i.defeated=false;R.G.impassable='vestry'
 expect('already occupied impassable location permits ability',R.takeStory(i,act) and R.G.metrics.clues_spent==3)
 expect('held story cannot be acquired twice',not R.takeStory(i,act) and R.G.metrics.clues_spent==3)
 FX.dropStory(i,R.G.locs.belfry);i.loc='vestry'
 expect('dropped story requires actual dropped location',not R.takeStory(i,act) and act.dropped=='belfry')
 i.loc='belfry'
 expect('dropped story pickup pays no second fare',R.takeStory(i,act) and act.dropped==nil and R.G.metrics.clues_spent==3)
end)
case('unchanged timed delivery',function()
 local R,FX,AI,st,act,i=fixture(1,'sthr-act-whythirteen');i.clues=3;assert(R.takeStory(i,act));i.loc='belfry'
 expect('surface arrival still waits for Hour advance',FX.canAdvance(act)==nil and not act.completed)
 R.rewind(1,'fixture');expect('surface rewind does not deliver',not act.completed)
 R.G.rememberEnding=R.G.round;R.advance(2,'canceled skip')
 expect('surface canceled skip does not deliver',not act.completed and act.holder==i)
 R.advance(1,'actual advance');expect('surface actual advance delivers',act.completed and i.story==nil)
 R,FX,AI,st,act,i=fixture(1,'sthr-act-hourwaswrong');i.clues=3;assert(R.takeStory(i,act));i.loc='vestry'
 R.checkObjectives();expect('deep still delivers immediately on arrival',act.completed and i.story==nil)
end)
case('Road failure returns exact new cost and reaction conditions',function()
 local R,FX,AI,st,act,i,counts=fixture(2,'sthr-act-walksbeside');i.clues=3;R.G.inv[2].clues=3
 local en={id='echo',loc='turning',exhausted=false,damage=0,def={traits='Echo.',fight=3}};R.G.enemies={en}
 R.test=function() return false,-1,'-2' end;R.standFirm(i,en)
 local _,returned=counts()
 expect('failed Stand Firm returns exactly six to Turning',returned==6 and R.G.metrics.clues_spent==6 and not act.completed and not en.exhausted)
 R,FX,AI,st,act,i=fixture(1,'sthr-act-walksbeside');i.clues=3;R.G.walksBesideCurrent=true
 FX.onEvade(i,{loc='turning',def={traits='Humanoid.'}})
 expect('Road reaction still requires Echo',not act.completed and i.clues==3)
 FX.onEvade(i,{loc='hub',def={traits='Echo.'}})
 expect('Road reaction still requires Turning',not act.completed and i.clues==3)
end)
case('final carry-policy and missing-drop hardening',function()
 local R,FX,AI,st,act,i=fixture(1,'sthr-act-whythirteen');i.clues=3;i.story={id='sthr-item-drownedpage'}
 local choice=AI.choose(i)
 expect('AI does not select another story under declared policy',not choice or choice.kind~='objective')
 i.story=nil;act.dropped='missing-guid'
 expect('missing drop cannot fall back to initial pickup',not R.takeStory(i,act) and act.dropped=='missing-guid' and not act.holder and not i.story and i.clues==3 and R.G.metrics.clues_spent==0)
end)
print(string.format('INDEPENDENT BALANCE COSTS: %d passed, %d failed',passed,failed))
if failed>0 then os.exit(1) end
