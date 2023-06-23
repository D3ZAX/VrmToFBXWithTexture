bl_info = {
    "name": "Vrm to FBX with Texture",
    "author": "D3LN",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > N",
    "description": "Export FBX format model from vrm model",
    "category": "",
}

import os
import bpy
from bpy import context

def unpack_node_img(node):
    img = node.image
    if img.packed_file != None:
        img = node.image.copy()
        img.name = "VrmToFBX_Img_" + img.name
        img.unpack(method='USE_LOCAL')
    return img

def copy_vrm(context):
    scene = context.scene
    objs_mat_copy = {}
    for obj in scene.objects:
        if obj.type == "MESH":
            # visit materials to unpack textures
            mats = obj.data.materials
            for i in range(len(mats)):
                mat = mats[i]

                if not mat.use_nodes:
                    continue
                
                base_color_img = None

                #Defining node variables
                nodes = mat.node_tree.nodes
                output = next((n for n in nodes if isinstance(n, bpy.types.ShaderNodeOutputMaterial)), None)

                for n in nodes:
                    if isinstance(n, bpy.types.ShaderNodeTexImage):
                        if n.name == "Mtoon1BaseColorTexture.Image":
                            base_color_img = unpack_node_img(n)
                            break

                #Checking for Mixshader/Output state
                if base_color_img is None or output is None:
                    continue

                if obj not in objs_mat_copy:
                    objs_mat_copy[obj] = {}
                obj_mats = objs_mat_copy[obj]

                mat_new = bpy.data.materials.new(name = "VrmToFBX_Mat_" + mat.name)
                mat_new.blend_method = mat.blend_method
                mat_new.use_backface_culling = mat.use_backface_culling
                mat_new.use_nodes = True
                node_tree_new = mat_new.node_tree
                nodes_new = node_tree_new.nodes
                output = nodes_new.get('Material Output')
                #Creating Principled node
                principled = nodes_new.get("Principled BSDF")

                base_color = nodes_new.new(type = "ShaderNodeTexImage")
                base_color.location = (principled.location[0] - 300, principled.location[1])
                base_color.image = base_color_img
                node_tree_new.links.new(base_color.outputs[0], principled.inputs[0])
                node_tree_new.links.new(base_color.outputs[1], principled.inputs[21])

                obj_mats[i] = mat_new

    collection = bpy.data.collections.new(name = "VrmToFBX_Collection")
    scene.collection.children.link(collection)
    objs_copy = {}
    # copy object
    for obj in objs_mat_copy:
        obj_new = obj.copy()
        obj_new.name = "VrmToFBX_Obj_" + obj.name
        obj_new.data = obj.data.copy()
        objs_copy[obj] = obj_new
        collection.objects.link(obj_new)

        obj_mats = objs_mat_copy[obj]
        for i in obj_mats:
            obj_new.material_slots[i].material = obj_mats[i]
    # copy object parent
    for obj in objs_mat_copy:
        copy_obj = objs_copy[obj]
        p = copy_obj.parent
        while p != None:
            if p in objs_copy:
                copy_obj.parent = objs_copy[p]
                p = None
            else:
                copy_p = p.copy()
                objs_copy[p] = copy_p
                collection.objects.link(copy_p)
                copy_obj.parent = copy_p
                p = copy_p.parent
    # change armature modifier object
    for obj in objs_copy:
        for modifier in objs_copy[obj].modifiers:
            if isinstance(modifier, bpy.types.ArmatureModifier):
                if modifier.object in objs_copy:
                    modifier.object = objs_copy[modifier.object]

def clear_copied(context):
    scene = context.scene
    for collection in scene.collection.children:
        if collection.name.startswith("VrmToFBX_Collection"):
            for obj in collection.objects:
                if obj.type == "MESH":
                    for mat in obj.data.materials:
                        if mat.name.startswith("VrmToFBX_Mat_"):
                            for n in mat.node_tree.nodes:
                                if isinstance(n, bpy.types.ShaderNodeTexImage):
                                    if n.image.name.startswith("VrmToFBX_Img_"):
                                        bpy.data.images.remove(n.image)
                            bpy.data.materials.remove(mat)
                    bpy.data.meshes.remove(obj.data)
                else:
                    bpy.data.objects.remove(obj)
            bpy.data.collections.remove(collection)
    delete_dir = True
    texture_path = bpy.path.abspath("//textures")
    if os.path.exists(texture_path):
        for file in os.listdir(texture_path):
            if file.startswith("VrmToFBX_Img_"):
                os.remove(os.path.join(texture_path, file))
            else:
                delete_dir = False
        if delete_dir:
            os.rmdir(texture_path)

# Helper to list all LayerCollections in the view layer recursively
def all_layer_collections(view_layer):
    stack = [view_layer.layer_collection]
    while stack:
        lc = stack.pop()
        yield lc
        stack.extend(lc.children)

def export_copied(context):
    scene = context.scene

    bpy.ops.object.mode_set()

    for obj in context.selected_objects:
        obj.select_set(False)

    for collection in scene.collection.children:
        if collection.name.startswith("VrmToFBX_Collection"):
            for lc in all_layer_collections(context.view_layer):
                if lc.collection.name == collection.name:
                    if not lc.exclude:
                        for obj in collection.objects:
                            obj.select_set(True)

    path = scene.export_vrm_to_fbx_path
    bpy.ops.export_scene.fbx('INVOKE_DEFAULT', filepath=path, path_mode='COPY', embed_textures=True, use_selection=True)

def export_copied_directly(context):
    scene = context.scene

    bpy.ops.object.mode_set()

    old_sel = []
    old_active = context.view_layer.objects.active

    for obj in context.selected_objects:
        old_sel.append(obj)
        obj.select_set(False)

    for collection in scene.collection.children:
        if collection.name.startswith("VrmToFBX_Collection"):
            for lc in all_layer_collections(context.view_layer):
                if lc.collection.name == collection.name:
                    if not lc.exclude:
                        for obj in collection.objects:
                            obj.select_set(True)

    # p_name = os.path.basename(bpy.data.filepath).replace(".blend", "")
    # path = bpy.path.abspath("//") + "./VrmToFBX_" + p_name + ".fbx"
    path = scene.export_vrm_to_fbx_path
    bpy.ops.export_scene.fbx(filepath=path, path_mode='COPY', embed_textures=True, use_selection=True)
    context.view_layer.objects.active = old_active

    for obj in context.selected_objects:
        obj.select_set(False)

    for obj in old_sel:
        obj.select_set(True)

class CopyVrmForExportFBX(bpy.types.Operator):
    """Copy Vrm for export FBX"""
    bl_idname = "vrmtofbx.copy_vrm_for_export_fbx"
    bl_label = "Copy Vrm for export FBX"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        copy_vrm(context)

        return {'FINISHED'}
    
class ExportCopyedFBX(bpy.types.Operator):
    """Select Copyed model and export as FBX"""
    bl_idname = "vrmtofbx.export_copyed_fbx"
    bl_label = "Export Copyed FBX"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        export_copied(context)
        
        return {'FINISHED'}
    
class ClearCopyedFBXFromVrm(bpy.types.Operator):
    """Clear Copyed FBX from Vrm"""
    bl_idname = "vrmtofbx.clear_copyed_fbx_from_vrm"
    bl_label = "Clear Copyed FBX from Vrm"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        clear_copied(context)
        
        return {'FINISHED'}
    
class OneKeyToExportFBX(bpy.types.Operator):
    """One Key to Export FBX, will auto copy, export and clear"""
    bl_idname = "vrmtofbx.one_key_to_export_fbx"
    bl_label = "One Key To Export FBX"
    bl_options = {'REGISTER'}

    def execute(self, context):
        copy_vrm(context)
        export_copied_directly(context)
        clear_copied(context)
        
        return {'FINISHED', 'UNDO'}
    
class Panel(bpy.types.Panel):
    bl_label = "Vrm to FBX"
    bl_idname = "Vrm_to_FBX"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Vrm to FBX"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator(CopyVrmForExportFBX.bl_idname,text="Copy", icon='MENU_PANEL')
        row.operator(ExportCopyedFBX.bl_idname,text="Export", icon='MENU_PANEL')
        row.operator(ClearCopyedFBXFromVrm.bl_idname,text="Clear", icon='MENU_PANEL')
        col = layout.column()
        col.prop(context.scene, 'export_vrm_to_fbx_path')
        row = layout.row()
        row.operator(OneKeyToExportFBX.bl_idname,text="One key for all", icon='MENU_PANEL')

def menu_func(self, context):
    self.layout.operator(CopyVrmForExportFBX.bl_idname)
    self.layout.operator(ExportCopyedFBX.bl_idname)
    self.layout.operator(ClearCopyedFBXFromVrm.bl_idname)
    self.layout.operator(OneKeyToExportFBX.bl_idname)

def register():
    bpy.utils.register_class(CopyVrmForExportFBX)
    bpy.utils.register_class(ExportCopyedFBX)
    bpy.utils.register_class(ClearCopyedFBXFromVrm)
    path = "VrmToFBX.fbx"
    bpy.types.Scene.export_vrm_to_fbx_path = bpy.props.StringProperty \
    (
      name = "Export Path",
      default = path,
      description = "Define the fbx export path",
      subtype = 'FILE_PATH',
    )
    bpy.utils.register_class(OneKeyToExportFBX)
    bpy.utils.register_class(Panel)
    # bpy.types.VIEW3D_MT_object.append(menu_func)  # Adds the new operator to an existing menu.

def unregister():
    bpy.utils.unregister_class(CopyVrmForExportFBX)
    bpy.utils.unregister_class(ExportCopyedFBX)
    bpy.utils.unregister_class(ClearCopyedFBXFromVrm)
    del bpy.types.Scene.export_vrm_to_fbx_path
    bpy.utils.unregister_class(OneKeyToExportFBX)
    bpy.utils.unregister_class(Panel)
    # bpy.types.VIEW3D_MT_object.remove(menu_func)

# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()