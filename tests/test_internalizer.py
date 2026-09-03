import copy
import importlib.util
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as E
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
FIXTURES=Path(__file__).resolve().parent/'fixtures'
DEPENDENCY_FIXTURES=BASE/'dependency_text'
spec=importlib.util.spec_from_file_location('internalizer', BASE/'DependencyInternalizer.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
v=m.value

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
  self.dir=Path(self.tmp.name)
  self.a=E.parse(FIXTURES/'A.sbs').getroot(); self.b=E.parse(FIXTURES/'B.sbs').getroot()
 def write(self):
  self.ap=self.dir/'A.sbs'; self.bp=self.dir/'B.sbs'
  E.ElementTree(self.a).write(self.ap,encoding='UTF-8',xml_declaration=True)
  E.ElementTree(self.b).write(self.bp,encoding='UTF-8',xml_declaration=True)
 def plan(self):
  self.write(); return m.MergePlan(self.ap,self.bp,'1582391047')
 def canonical(self,e): return E.tostring(e)
 def remap_dep(self,root,old,new):
  for d in root.findall('./dependencies/dependency'):
   if v(d,'uid')==old:m.set_value(d,'uid',new)
  for p in m.references(root):
   path,dep=m.parse_reference(p)
   if dep==old:m.rewrite_reference(p,path,new)
 def dep(self,root,uid,path):
  d=E.SubElement(root.find('dependencies'),'dependency')
  for k,x in [('filename',path),('uid',uid),('type','package'),('fileUID','0'),('versionUID','0')]:m.set_value(d,k,x)
 def uid_for(self,root,filename):
  return next(v(dep,'uid') for dep in root.findall('./dependencies/dependency')
              if Path(v(dep,'filename')).name.lower()==filename.lower())
 def assert_only_builtin_or_packaged_external(self,p):
  self.assertIn('sbs://functions.sbs',p.external)
  self.assertTrue(all(path.startswith('sbs://') or m.is_packaged_dependency(path)
                      for path in p.external))
 def test_actual_pair_matches_accepted_result(self):
  p=self.plan(); accepted=E.parse(FIXTURES/'A_accepted.sbs').getroot()
  self.assertEqual(len(p.copied),6)
  self.assertEqual(p.connections_checked,204)
  self.assertEqual(self.canonical(p.root.find('./content/graph')),self.canonical(self.a.find('./content/graph')))
  ri=m.resource_index(p.root); ai=m.resource_index(accepted)
  for name in p.mapping.values():self.assertEqual(self.canonical(ri[name]),self.canonical(ai[name]))
  self.assertEqual(p.external,['sbs://functions.sbs'])
  out=p.save(self.dir/'result.sbs'); self.assertNotIn('B.sbs',Path(out).read_text(encoding='utf-8'))
 def test_different_self_uid(self):
  self.remap_dep(self.b,'1582391047','3210000000')
  p=self.plan()
  self.assertNotIn('dependency=3210000000',self.canonical(p.root).decode())
  self.assertEqual(p.connections_checked,204)
 def test_existing_self_and_same_name_collision(self):
  self.dep(self.a,'3200000000','?himself')
  grp=copy.deepcopy(self.b.find('./content/group'))
  # Existing same-named functions, including their original UIDs, must not be overwritten.
  self.a.find('content').append(grp)
  for ref in m.references(grp):
   path,dep=m.parse_reference(ref)
   if dep=='1582391047':m.rewrite_reference(ref,path,'3200000000')
  self.dep(self.a,'1290776887','sbs://functions.sbs')
  before=self.canonical(grp)
  p=self.plan()
  self.assertEqual(p.self_uid,'3200000000')
  self.assertTrue(all(x.endswith('_from_B') for x in p.mapping.values()))
  original=m.resource_index(p.root)['funtion/frac2']
  self.assertEqual(self.canonical(original),self.canonical(m.resource_index(self.a)['funtion/frac2']))
  # 6 new resources, original resources and original graph preserved.
  self.assertEqual(len([x for x in m.resource_index(p.root).values() if x.tag=='function']),12)
  self.assertTrue(any(k!=val for k,val in p.uid_map.items()))
  for ref in m.references(p.copied['funtion/signedNoise2DTiled']):
   path,dep=m.parse_reference(ref)
   if dep==p.self_uid:self.assertTrue(path.endswith('_from_B'))
 def test_constant_equal_to_colliding_uid_is_untouched(self):
  function=m.resource_index(self.b)['funtion/frac2']
  old=v(function,'uid')
  m.set_value(self.a.find('./content/graph'),'uid',old)
  constant=next(function.iter('constantValueString'))
  # Don't use a reference field: pick a get-variable string from the function.
  literal=E.SubElement(function,'description'); literal.set('v',old)
  p=self.plan()
  self.assertNotEqual(v(p.copied['funtion/frac2'],'uid'),old)
  self.assertEqual(v(p.copied['funtion/frac2'],'description'),old)
 def test_group_name_collides_with_graph(self):
  graph=E.SubElement(self.a.find('content'),'graph')
  m.set_value(graph,'identifier','funtion');m.set_value(graph,'uid','123111')
  p=self.plan()
  self.assertTrue(all(x.startswith('funtion_from_B/') for x in p.mapping.values()))
 def test_external_dependency_uid_conflict(self):
  self.dep(self.a,'1290776887','some_other_package.sbs')
  p=self.plan()
  deps=m.dependency_index(p.root)
  self.assertTrue(v(deps['1290776887'],'filename').endswith('some_other_package.sbs'))
  builtin=next(uid for uid,d in deps.items() if v(d,'filename')=='sbs://functions.sbs')
  self.assertNotEqual(builtin,'1290776887')
  for ref in m.references(p.copied['funtion/frac2']):
   path,dep=m.parse_reference(ref)
   if path.startswith('Functions/'):self.assertEqual(dep,builtin)
 def test_external_relative_path_rebased(self):
  self.dep(self.b,'3210000001','sub/C.sbs')
  ref=next(m.references(m.resource_index(self.b)['funtion/frac2']))
  m.rewrite_reference(ref,'SomeFunction','3210000001')
  p=self.plan()
  self.assertTrue(any(m.dependency_key(x,p.host.path)==m.dependency_key('sub/C.sbs',p.source.path)
                      for x in p.external))
 def test_recursive_disk_dependency_chain(self):
  for name in ('A.sbs','B.sbs','C.sbs','D.sbs'):
   shutil.copy2(DEPENDENCY_FIXTURES/name,self.dir/name)
  p=m.MergePlan(self.dir/'A.sbs',self.dir/'B.sbs',self.uid_for(E.parse(self.dir/'A.sbs').getroot(),'B.sbs'))
  self.assertEqual({Path(d.path).name for d in p.documents.values()},{'B.sbs','C.sbs','D.sbs'})
  origins={(Path(p.documents[key].path).name,path) for key,path in p.resource_mapping}
  self.assertEqual(origins,{
   ('B.sbs','funtion/fbmLine2DTiled'),
   ('C.sbs','funtion/signedNoise2DTiled'),
   ('C.sbs','funtion/frac2'),
   ('C.sbs','funtion/hash21Tiled'),
   ('D.sbs','funtion/hash21Tiled'),
  })
  self.assert_only_builtin_or_packaged_external(p)
  package_name=lambda key: 'A.sbs' if key==p.host_key else Path(p.documents[key].path).name
  edges={(package_name(parent),package_name(child))
         for parent,children in p.package_edges.items() for child in children}
  self.assertEqual(edges,{
   ('A.sbs','B.sbs'),('B.sbs','C.sbs'),('C.sbs','D.sbs')
  })
  dependency_files={v(dep,'filename') for dep in m.dependency_index(p.root).values()}
  self.assertFalse(dependency_files & {'B.sbs','C.sbs','D.sbs'})
  out=Path(p.save(self.dir/'recursive_result.sbs'))
  result=m.Document(out)
  self.assertEqual(len(result.resources),12)  # Existing A plus five imported functions.
 def test_recursive_branches_and_cycle_are_deduplicated(self):
  roots={name:E.parse(DEPENDENCY_FIXTURES/name).getroot() for name in ('A.sbs','B.sbs','C.sbs','D.sbs')}
  # B reaches C and D directly.
  self.dep(roots['B.sbs'],'4000000001','D.sbs')
  b_nodes=m.resource_index(roots['B.sbs'])['funtion/fbmLine2DTiled'].find('.//paramNodes')
  b_ref=E.SubElement(b_nodes,'paramNode');m.set_value(b_ref,'uid','4000000002')
  m.set_value(b_ref,'function','instance');m.set_value(b_ref,'type','118772')
  data=E.SubElement(E.SubElement(b_ref,'funcDatas'),'funcData');m.set_value(data,'name','instance')
  E.SubElement(E.SubElement(data,'constantValue'),'constantValueString',
               v='pkg:///funtion/hash11Tiled?dependency=4000000001')
  # C -> D points to hash11Tiled, and hash11Tiled points back to C.
  c_fn=m.resource_index(roots['C.sbs'])['funtion/signedNoise2DTiled']
  for c_to_d in [p for p in m.references(c_fn) if m.parse_reference(p)[1]=='1580458636']:
   m.rewrite_reference(c_to_d,'funtion/hash11Tiled','1580458636')
  d_nodes=m.resource_index(roots['D.sbs'])['funtion/hash11Tiled'].find('.//paramNodes')
  d_ref=E.SubElement(d_nodes,'paramNode');m.set_value(d_ref,'uid','4000000003')
  m.set_value(d_ref,'function','instance');m.set_value(d_ref,'type','118772')
  data=E.SubElement(E.SubElement(d_ref,'funcDatas'),'funcData');m.set_value(data,'name','instance')
  E.SubElement(E.SubElement(data,'constantValue'),'constantValueString',
               v='pkg:///funtion/signedNoise2DTiled?dependency=1582391047')
  for name,root in roots.items():
   E.ElementTree(root).write(self.dir/name,encoding='UTF-8',xml_declaration=True)
  p=m.MergePlan(self.dir/'A.sbs',self.dir/'B.sbs',self.uid_for(roots['A.sbs'],'B.sbs'))
  origins={(Path(p.documents[key].path).name,path) for key,path in p.resource_mapping}
  self.assertEqual(origins,{
   ('B.sbs','funtion/fbmLine2DTiled'),
   ('C.sbs','funtion/signedNoise2DTiled'),
   ('C.sbs','funtion/frac2'),
   ('C.sbs','funtion/hash21Tiled'),
   ('D.sbs','funtion/hash11Tiled'),
  })
  self.assert_only_builtin_or_packaged_external(p)
 def test_auto_discovers_all_editable_host_dependencies(self):
  for name in ('A.sbs','B.sbs','C.sbs','D.sbs'):
   shutil.copy2(DEPENDENCY_FIXTURES/name,self.dir/name)
  p=m.MergePlan(self.dir/'A.sbs')
  expected={self.uid_for(E.parse(self.dir/'A.sbs').getroot(),name) for name in ('B.sbs','C.sbs')}
  self.assertEqual({uid for uid,_ in p.root_sources},expected)
  self.assertEqual({Path(doc.path).name for _,doc in p.root_sources},{'B.sbs','C.sbs'})
  self.assert_only_builtin_or_packaged_external(p)
  self.assertTrue(all(m.is_packaged_dependency(path)
                      for paths in p.retained_by_package.values() for path in paths))
 def test_replace_policy_applies_at_each_merge_stage(self):
  for name in ('A.sbs','B.sbs','C.sbs','D.sbs'):
   shutil.copy2(DEPENDENCY_FIXTURES/name,self.dir/name)
  p=m.MergePlan(self.dir/'A.sbs',collision_policy='replace')
  def package_name(key):return 'A.sbs' if key==p.host_key else Path(p.documents[key].path).name
  replaced={(package_name(parent),package_name(child),Path(p.documents[origin].path).name,path)
            for parent,child,origin,path in p.replaced}
  self.assertIn(('C.sbs','D.sbs','D.sbs','funtion/hash21Tiled'),replaced)
  self.assertIn(('A.sbs','B.sbs','D.sbs','funtion/hash21Tiled'),replaced)
  self.assertIn(('A.sbs','B.sbs','C.sbs','funtion/frac2'),replaced)
  mapping={(Path(p.documents[key].path).name,path):target
           for (key,path),target in p.resource_mapping.items()}
  self.assertEqual(mapping[('C.sbs','funtion/frac2')],'funtion/frac2')
  self.assertEqual(mapping[('C.sbs','funtion/hash21Tiled')],'funtion/hash21Tiled')
  self.assertEqual(mapping[('D.sbs','funtion/hash21Tiled')],'funtion/hash21Tiled')
  self.assert_only_builtin_or_packaged_external(p)
 def test_per_resource_collision_override(self):
  for name in ('A.sbs','B.sbs','C.sbs','D.sbs'):
   shutil.copy2(DEPENDENCY_FIXTURES/name,self.dir/name)
  initial=m.MergePlan(self.dir/'A.sbs')
  frac=next(token for token in initial.collision_candidates
            if token[0]==initial.host_key
            and Path(initial.documents[token[2]].path).name=='C.sbs'
            and token[3]=='funtion/frac2')
  p=m.MergePlan(self.dir/'A.sbs',collision_overrides={frac})
  self.assertEqual(p.replaced,{frac})
  mapping={(Path(p.documents[key].path).name,path):target
           for (key,path),target in p.resource_mapping.items()}
  self.assertEqual(mapping[('C.sbs','funtion/frac2')],'funtion/frac2')
  self.assertEqual(mapping[('C.sbs','funtion/hash21Tiled')],'funtion/hash21Tiled_from_C')
 def test_generation_log_records_bottom_up_steps(self):
  for name in ('A.sbs','B.sbs','C.sbs','D.sbs'):
   shutil.copy2(DEPENDENCY_FIXTURES/name,self.dir/name)
  p=m.MergePlan(self.dir/'A.sbs')
  lines=p.generation_log(self.dir/'final.sbs')
  steps=[line for line in lines if line.startswith('步骤')]
  self.assertIn('D.sbs → C.sbs',steps[0])
  self.assertIn('C.sbs → B.sbs',steps[1])
  self.assertIn('B.sbs → A.sbs',steps[2])
  self.assertIn('写出最终包',steps[3])
  self.assertTrue(any('更名为 funtion/hash21Tiled_from_D' in line for line in lines))
 def test_english_ui_and_generation_log(self):
  for name in ('A.sbs','B.sbs','C.sbs','D.sbs'):
   shutil.copy2(DEPENDENCY_FIXTURES/name,self.dir/name)
  p=m.MergePlan(self.dir/'A.sbs')
  text='\n'.join(m.localize_text(line,'en') for line in p.log+p.generation_log(self.dir/'final.sbs'))
  self.assertIn('Generation steps:',text)
  self.assertIn('Step 1',text)
  self.assertIn('write final package',text)
  summary='\n'.join(m.localize_text(line,'en') for line in p.log[:4])
  self.assertFalse(any('\u4e00'<=char<='\u9fff' for char in summary))
  self.assertEqual(m.ui_text('analyze','en'),'1. Analyze')
 def test_packaged_dependency_is_migrated_and_rewritten_relative(self):
  package=self.dir/'compiled.sbsar';package.write_bytes(b'compiled-package')
  self.dep(self.b,'3210000001',str(package))
  ref=next(m.references(m.resource_index(self.b)['funtion/frac2']))
  m.rewrite_reference(ref,'SomeGraph','3210000001')
  p=self.plan()
  out=Path(p.save(self.dir/'result.sbs'))
  migrated=self.dir/'result_dependencies'/'compiled.sbsar'
  self.assertEqual(migrated.read_bytes(),b'compiled-package')
  result=m.Document(out)
  dep=next(d for d in result.deps.values() if v(d,'filename').endswith('compiled.sbsar'))
  self.assertEqual(v(dep,'filename'),'result_dependencies/compiled.sbsar')
  self.assertTrue(any('迁移编译依赖' in line for line in p.generation_log(out)))
 def test_packaged_dependency_does_not_overwrite_existing_directory(self):
  package=self.dir/'compiled.sbser';package.write_bytes(b'compiled-package')
  self.dep(self.b,'3210000001',str(package))
  ref=next(m.references(m.resource_index(self.b)['funtion/frac2']))
  m.rewrite_reference(ref,'SomeGraph','3210000001')
  p=self.plan();(self.dir/'result_dependencies').mkdir()
  with self.assertRaises(m.MergeError):p.save(self.dir/'result.sbs')
  self.assertFalse((self.dir/'result.sbs').exists())
 def test_packaged_dependency_only_mode(self):
  package=self.dir/'only.sbsar';package.write_bytes(b'compiled-only')
  self.dep(self.a,'3210000001',str(package))
  # Point A's existing external instance to the compiled dependency, leaving no editable SBS input.
  for ref in m.references(self.a):
   path,dep=m.parse_reference(ref)
   if dep=='1582391047':m.rewrite_reference(ref,path,'3210000001')
  self.write()
  p=m.MergePlan(self.ap)
  self.assertEqual(p.merge_steps,[])
  out=Path(p.save(self.dir/'portable.sbs'))
  self.assertTrue((self.dir/'portable_dependencies'/'only.sbsar').is_file())
  result=m.Document(out)
  self.assertTrue(any(v(dep,'filename')=='portable_dependencies/only.sbsar'
                      for dep in result.deps.values()))
 def test_only_transitively_needed_functions_are_copied(self):
  nodes=self.a.find('.//dynamicValue/paramNodes')
  for n in list(nodes):
   if v(n,'function')=='instance':nodes.remove(n)
  fn=E.SubElement(nodes,'paramNode'); m.set_value(fn,'uid','1000000010');m.set_value(fn,'function','instance');m.set_value(fn,'type','118772')
  data=E.SubElement(E.SubElement(fn,'funcDatas'),'funcData');m.set_value(data,'name','instance')
  E.SubElement(E.SubElement(data,'constantValue'),'constantValueString',v='pkg:///funtion/fbmLine2DTiled?dependency=1582391047')
  m.set_value(self.a.find('.//dynamicValue'),'rootnode','1000000010')
  p=self.plan()
  self.assertEqual(set(p.copied),{'funtion/fbmLine2DTiled','funtion/signedNoise2DTiled','funtion/hash21Tiled','funtion/frac2'})
 def test_missing_resource_fails_before_writing(self):
  grp=self.b.find('./content/group/content')
  grp.remove(next(f for f in grp if v(f,'identifier')=='frac2'))
  with self.assertRaises(m.MergeError):self.plan()
  self.assertFalse((self.dir/'result.sbs').exists())
 def test_unsupported_resource_fails(self):
  f=m.resource_index(self.b)['funtion/frac2'];f.tag='resource'
  with self.assertRaises(m.MergeError):self.plan()
 def test_input_files_unchanged_and_no_overwrite(self):
  p=self.plan();before=(self.ap.read_bytes(),self.bp.read_bytes())
  with self.assertRaises(m.MergeError):p.save(self.ap)
  out=self.dir/'out.sbs';p.save(out)
  with self.assertRaises(m.MergeError):p.save(out)
  self.assertEqual(before,(self.ap.read_bytes(),self.bp.read_bytes()))
 def test_input_modified_after_analysis(self):
  p=self.plan();self.bp.write_bytes(self.bp.read_bytes()+b'\n')
  with self.assertRaises(m.MergeError):p.save(self.dir/'out.sbs')
 def test_input_interface_mismatch_fails(self):
  f=m.resource_index(self.b)['funtion/fbmLine2DTiled'];m.set_value(f.find('./paraminputs/paraminput'),'identifier','different')
  with self.assertRaises(m.MergeError):self.plan()
 def test_graph_mult_output_bridging_with_uid_collisions(self):
  bb=m.resource_index(self.b)['BB']
  out2=copy.deepcopy(bb.find('./graphOutputs/graphoutput'))
  m.set_value(out2,'identifier','roughness');m.set_value(out2,'uid','1582393127');bb.find('graphOutputs').append(out2)
  # This UID collides with an existing A node output. Remapping must touch B only.
  n2=copy.deepcopy(bb.find('./compNodes/compNode'))
  m.set_value(n2,'uid','1582402461');m.set_value(n2.find('./compImplementation/compOutputBridge'),'output','1582393127');bb.find('compNodes').append(n2)
  comp=E.SubElement(self.a.find('./content/graph/compNodes'),'compNode');m.set_value(comp,'uid','2100000000')
  outs=E.SubElement(comp,'compOutputs')
  impl=E.SubElement(E.SubElement(comp,'compImplementation'),'compInstance');m.set_value(impl,'path','pkg:///BB?dependency=1582391047')
  bridges=E.SubElement(impl,'outputBridgings')
  for uid,name in [('2100000001','base_color'),('2100000002','roughness')]:
   o=E.SubElement(outs,'compOutput');m.set_value(o,'uid',uid);m.set_value(o,'comptype','1')
   bridge=E.SubElement(bridges,'outputBridging');m.set_value(bridge,'uid',uid);m.set_value(bridge,'identifier',name)
  conn=self.a.find('./content/graph/compNodes/compNode/connections/connection')
  m.set_value(conn,'connRef','2100000000');m.set_value(conn,'connRefOutput','2100000002')
  before=self.canonical(comp)
  p=self.plan()
  self.assertEqual(self.canonical(list(p.root.find('./content/graph/compNodes'))[-1]),before)
  imported=p.copied['BB']
  self.assertNotEqual(v(imported.find('./graphOutputs/graphoutput'),'uid'),'1560442737')
  self.assertEqual(v(list(imported.find('compNodes'))[1].find('./compImplementation/compOutputBridge'),'output'),p.uid_map['1582393127'])

if __name__=='__main__':unittest.main(verbosity=2)
