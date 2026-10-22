import importlib.util,json,pathlib,sys,copy
fixture,workspace=sys.argv[1:];root=pathlib.Path(workspace);target="label.py" if fixture=="A" else "counter.py";spec=importlib.util.spec_from_file_location("candidate",root/target);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);checks=[]
def check(name,fn):
 try:fn();checks.append({"name":name,"pass":True})
 except Exception as ex:checks.append({"name":name,"pass":False,"error":type(ex).__name__+": "+str(ex)})
def eq(a,b):
 assert a==b,(a,b)
def raises(kind,fn):
 try:fn()
 except kind:return
 raise AssertionError("expected "+kind.__name__)
if fixture=="A":
 for name,x,want in [("latest_blank","","Untitled"),("latest_spaces"," \t\n","Untitled"),("edge_trim","  Alpha Beta  ","Alpha Beta"),("internal_whitespace"," A  B ","A  B"),("case"," lowerCASE ","lowerCASE"),("unicode"," \u2003 Ω ","Ω")]:check(name,lambda x=x,want=want:eq(m.label(x),want))
 check("invalid_none",lambda:raises(TypeError,lambda:m.label(None)));check("invalid_int",lambda:raises(TypeError,lambda:m.label(42)))
else:
 check("latest_default",lambda:eq(m.apply({"count":3,"seen":[]},"x"),{"count":5,"seen":["x"]}))
 check("explicit_amount",lambda:eq(m.apply({"count":1,"seen":[]},"x",4)["count"],5))
 check("duplicate_effect",lambda:eq(m.apply(m.apply({"count":0,"seen":[]},"same"),"same"),{"count":2,"seen":["same"]}))
 check("preserved_fields",lambda:eq(m.apply({"count":0,"seen":[],"extra":{"x":1}},"k")["extra"],{"x":1}))
 def purity():
  s={"count":4,"seen":["a"]};before=copy.deepcopy(s);m.apply(s,"b");eq(s,before)
 check("purity",purity);check("zero",lambda:eq(m.apply({"count":4,"seen":[]},"z",0)["count"],4));check("negative",lambda:raises(ValueError,lambda:m.apply({"count":0,"seen":[]},"x",-1)));check("boolean",lambda:raises(TypeError,lambda:m.apply({"count":0,"seen":[]},"x",True)))
print(json.dumps({"fixture":fixture,"checks":checks,"passed":sum(x["pass"] for x in checks),"total":len(checks),"success":all(x["pass"] for x in checks)}));sys.exit(0 if all(x["pass"] for x in checks) else 1)
