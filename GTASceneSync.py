bl_info = {
    "name": "GTASceneSync (SA Only)",
    "author": "MadGamerHD",
    "version": (2, 3, 3),
    "blender": (4, 0, 0),
    "location": "View3D > UI > GTASceneSync",
    "description": "Export GTA San Andreas IDE and IPL from Blender, naming by collection and stripping .dff suffix",
    "category": "Import-Export",
}

import bpy
import re
import struct
import mathutils
from pathlib import Path

# ----------------------------
# Helper Functions
# ----------------------------

def clean_name(name: str) -> str:
    """Remove numeric suffixes from the model name."""
    return re.sub(r"\.\d+$", "", name)


def clean_collection_name(name: str) -> str:
    """Strip the .dff suffix from collection names."""
    return re.sub(r"\.dff$", "", name, flags=re.IGNORECASE)

# ----------------------------
# Operators: GTASceneSync
# ----------------------------
class ExportAsIDE(bpy.types.Operator):
    bl_idname = "export_scene.ide"
    bl_label = "Export Selected as IDE"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    model_id: bpy.props.IntProperty(name="Starting Model ID", default=4542)

    def draw(self, context):
        self.layout.prop(self, "model_id")

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            self.report({'WARNING'}, "No mesh objects selected.")
            return {'CANCELLED'}
        if not self.filepath.lower().endswith('.ide'):
            self.filepath += '.ide'

        # use operator model_id, otherwise fallback to scene default
        start_id = self.model_id or getattr(context.scene, "gtass_model_id", 4542)

        unique = {}
        cur = start_id
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                f.write('objs\n')
                for obj in objs:
                    coll = obj.users_collection[0] if obj.users_collection else None
                    base = clean_collection_name(coll.name) if coll else clean_name(obj.name)
                    props = obj.ide_flags
                    if base not in unique:
                        unique[base] = (cur, props.texture_name, props.render_distance, props.ide_flag)
                        cur += 1
                for name, (mid, txd, dist, flag) in unique.items():
                    f.write(f"{mid}, {name}, {txd}, {dist}, {flag}\n")
                f.write('end\n')
        except Exception as e:
            self.report({'ERROR'}, f"IDE export failed: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"IDE export complete: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        # prefill operator model_id from scene setting
        if (not self.model_id or self.model_id == 4542) and hasattr(context.scene, "gtass_model_id"):
            self.model_id = context.scene.gtass_model_id
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class ExportAsIPL(bpy.types.Operator):
    bl_idname = "export_scene.ipl"
    bl_label = "Export Selected as IPL"
    bl_options = {'REGISTER'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    model_id: bpy.props.IntProperty(name="Starting Model ID", default=4542)
    apply_default_rotation: bpy.props.BoolProperty(name="Apply Default Rotation", default=False)
    default_rotation: bpy.props.FloatVectorProperty(name="Default Rotation (Euler)", subtype='EULER', default=(0,0,0))
    # Removed binary export option: always exports ASCII .ipl

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'model_id')
        layout.prop(self, 'apply_default_rotation')
        if self.apply_default_rotation:
            layout.prop(self, 'default_rotation')

    def validate_filepath(self):
        p = Path(self.filepath)
        if p.suffix.lower() != '.ipl':
            p = p.with_suffix('.ipl')
        self.filepath = str(p)

    def generate_mapping(self, objs):
        mapping, cur = {}, self.model_id or bpy.context.scene.gtass_model_id
        for o in objs:
            # Prefer collection name if present, otherwise cleaned object name
            coll = o.users_collection[0] if o.users_collection else None
            name = clean_collection_name(coll.name) if coll else clean_name(o.name)
            name = name or 'Unnamed'
            if name not in mapping:
                mapping[name] = cur
                cur += 1
        return mapping

    def write_ipl(self, f, objs, mapping):
        inter, lod = 0, -1
        fmt = lambda v: f"{v:.6f}"
        # Always write ASCII .ipl (normal mode). Binary export removed.
        f.write('# Exported with GTASceneSync\ninst\n')
        for obj in objs:
            wm = obj.matrix_world
            pos = wm.to_translation(); base = wm.to_quaternion()
            if self.apply_default_rotation:
                off = mathutils.Euler(self.default_rotation,'XYZ').to_quaternion()
                base = off @ base
            rx, ry, rz, rw = -base.x, base.y, -base.z, base.w
            coll = obj.users_collection[0] if obj.users_collection else None
            nm = clean_collection_name(coll.name) if coll else clean_name(obj.name)
            nm = nm or 'Unnamed'
            mid = mapping.get(nm, -1)
            f.write(
                f"{mid}, {nm}, {inter}, {fmt(pos.x)}, {fmt(pos.y)}, {fmt(pos.z)}, {fmt(rx)}, {fmt(ry)}, {fmt(rz)}, {fmt(rw)}, {lod}\n"
            )
        f.write('end\n')

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            self.report({'WARNING'}, "No mesh objects selected.")
            return {'CANCELLED'}
        self.validate_filepath()
        mapping = self.generate_mapping(objs)
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                self.write_ipl(f, objs, mapping)
        except Exception as e:
            self.report({'ERROR'}, f"IPL export failed: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"IPL export complete: {self.filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        if (not self.model_id or self.model_id == 4542) and hasattr(context.scene, "gtass_model_id"):
            self.model_id = context.scene.gtass_model_id
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# ----------------------------
# Operators: Utilities
# ----------------------------
class OBJECT_OT_batch_rename(bpy.types.Operator):
    """Renames selected objects with a base name followed by numbers"""
    bl_idname = "object.batch_rename"
    bl_label = "Batch Rename Objects"
    bl_options = {"REGISTER", "UNDO"}

    base_name: bpy.props.StringProperty(
        name="Base Name",
        description="Base name for renaming objects",
        default="TypeName",
    )

    def execute(self, context):
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({"WARNING"}, "No objects selected!")
            return {"CANCELLED"}
        for i, obj in enumerate(selected_objects, start=1):
            obj.name = f"{self.base_name}_{i}"
        return {"FINISHED"}

class OBJECT_OT_reset_position(bpy.types.Operator):
    """Sets the position of selected objects to (0, 0, 0)"""
    bl_idname = "object.reset_position"
    bl_label = "Reset Position"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({"WARNING"}, "No objects selected!")
            return {"CANCELLED"}
        for obj in selected_objects:
            obj.location = (0, 0, 0)
        return {"FINISHED"}

class OBJECT_OT_remove_materials(bpy.types.Operator):
    """Removes all materials from selected objects"""
    bl_idname = "object.remove_materials"
    bl_label = "Remove All Materials"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({"WARNING"}, "No objects selected!")
            return {"CANCELLED"}
        for obj in selected_objects:
            if obj.type == "MESH":
                obj.data.materials.clear()
        self.report({'INFO'}, "Materials removed from selected objects.")
        return {"FINISHED"}

# ----------------------------
# DFF property group (restores original 'dff' behavior safely)
# ----------------------------
class DFFProperties(bpy.types.PropertyGroup):
    type: bpy.props.EnumProperty(
        name="DFF Type",
        items=[('','None','No DFF type'), ('COL','Collision','Collision object')],
        default=''
    )

class OBJECT_OT_convert_to_collision(bpy.types.Operator):
    """Convert selected objects to Collision Object (tags them, doesn't change meshes)"""
    bl_idname = "object.convert_to_collision"
    bl_label = "Convert to Collision Object"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({"WARNING"}, "No objects selected!")
            return {"CANCELLED"}
        count = 0
        for obj in selected_objects:
            if obj.type == "MESH":
                # Use the registered PointerProperty (DFFProperties) to mark this as collision
                try:
                    obj.dff.type = 'COL'
                    count += 1
                except Exception:
                    # As a fallback, write a custom property for compatibility
                    obj["dff_type"] = "COL"
                    count += 1
        self.report({'INFO'}, f"Marked {count} objects as collision objects.")
        return {"FINISHED"}

# ----------------------------
# PropertyGroup
# ----------------------------
IDE_FLAGS = [
    # Basic Flags (all models except peds/vehicles)
    ("4", "Draw Last", "Draw after opaque geometry. Automatically applies Additive."),
    ("8", "Additive", "Additive blending."),
    ("64", "No Z-Write", "Do not write to Z buffer (e.g., static shadow models)."),
    ("128", "No Shadows", "Shadows will not be cast on this model."),
    ("2097152", "No Backface Culling", "Disables backface culling."),

    # Clump Flags (animated/clump models only)
    ("32", "Door", "This model is a door."),

    # Atomic Flags (Mutually Exclusive)
    ("512", "Code Glass", "Breakable glass. Texture changes when broken. Requires object.dat."),
    ("1024", "Artist Glass", "Breakable glass. Texture does not change when broken. Requires object.dat."),
    ("2048", "Garage Door", "Identifies the model as a garage door."),
    ("8192", "Tree", "Normal tree affected by wind."),
    ("16384", "Palm Tree", "Palm tree affected by wind."),
    ("1048576", "Tag", "Sprayable tag; switches mesh when sprayed."),
    ("4194304", "No Cover", "Peds cannot take cover behind this model."),
    ("8388608", "Wet Only", "Wet only model."),

    # Atomic Flags (Non-Mutually Exclusive)
    ("1", "Wet Roads", "Use wet road reflections."),
    ("4096", "Damageable", "Has a damaged version (e.g., custom car components). Cannot be used by timed atomic models."),
    ("32768", "No Flyer Collide", "Prevents destruction by planes/helicopters (approximate)."),

    # Default flag
    ("0", "(SA)Default", "No special flags")
]

class IDEFlagsProperties(bpy.types.PropertyGroup):
    ide_flag: bpy.props.EnumProperty(name="IDE Flag", items=IDE_FLAGS, default='0')
    render_distance: bpy.props.IntProperty(name="Render Distance", default=299, min=0, max=1200)
    texture_name: bpy.props.StringProperty(name="Texture Name", default='generic')

# ----------------------------
# UI Panel
# ----------------------------
class GTASceneSyncUIPanel(bpy.types.Panel):
    bl_label = "GTASceneSync"
    bl_idname = "VIEW3D_PT_gtascenesync"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GTASceneSync'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        sel_mesh_count = sum(1 for o in context.selected_objects if o.type=='MESH')

        # Utility Tools
        layout.label(text="Utilities:")
        row = layout.row(align=True)
        row.prop(scene, 'batch_rename_base_name', text='Rename Base')
        row.operator(OBJECT_OT_batch_rename.bl_idname, text='Rename')
        row = layout.row(align=True)
        row.operator(OBJECT_OT_reset_position.bl_idname, text='Reset Pos')
        row = layout.row(align=True)
        row.operator(OBJECT_OT_remove_materials.bl_idname, text='Remove Mats')
        row = layout.row(align=True)
        row.operator(OBJECT_OT_convert_to_collision.bl_idname, text='To Collision')
        layout.separator()

        # Batch TXD
        layout.label(text="Batch assign TXD for selected:")
        layout.prop(scene, 'batch_txd_name', text='TXD Name')
        layout.operator('gtascenesync.batch_txd', text='Set TXD')
        layout.separator()

        # Per-object settings
        layout.label(text=f"Selected Objects: {sel_mesh_count}")
        for obj in context.selected_objects:
            if obj.type != 'MESH': continue
            box = layout.box()
            box.label(text=obj.name)
            box.prop(obj.ide_flags, 'texture_name', text='TXD')
            box.prop(obj.ide_flags, 'ide_flag', text='Flag')
            box.prop(obj.ide_flags, 'render_distance', text='Draw Dist')
        layout.separator()

        # Export buttons & defaults
        layout.label(text="Exports:")
        row = layout.row(align=True)
        row.prop(scene, 'gtass_model_id', text='Start ID')
        row = layout.row(align=True)
        # prefill operator properties with scene start ID so the file dialog opens with that ID
        op = row.operator(ExportAsIDE.bl_idname, text="Export IDE")
        op.model_id = scene.gtass_model_id
        op2 = row.operator(ExportAsIPL.bl_idname, text="Export IPL")
        op2.model_id = scene.gtass_model_id

# ----------------------------
# Batch TXD Operator
# ----------------------------
class BatchSetTXD(bpy.types.Operator):
    bl_idname = "gtascenesync.batch_txd"
    bl_label = "Set TXD for Selected"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        txd = context.scene.batch_txd_name.strip()
        if not txd:
            self.report({'WARNING'}, "TXD name is empty.")
            return {'CANCELLED'}
        count = 0
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                obj.ide_flags.texture_name = txd
                count += 1
        self.report({'INFO'}, f"Set TXD '{txd}' for {count} objects.")
        return {'FINISHED'}

# ----------------------------
# Registration
# ----------------------------
classes = [
    ExportAsIDE, ExportAsIPL, BatchSetTXD,
    OBJECT_OT_batch_rename, OBJECT_OT_reset_position,
    OBJECT_OT_remove_materials, OBJECT_OT_convert_to_collision,
    DFFProperties, IDEFlagsProperties, GTASceneSyncUIPanel
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.ide_flags = bpy.props.PointerProperty(type=IDEFlagsProperties)
    bpy.types.Object.dff = bpy.props.PointerProperty(type=DFFProperties)  # restored safe dff property
    bpy.types.Scene.batch_txd_name = bpy.props.StringProperty(name="Batch TXD Name", default="generic")
    bpy.types.Scene.batch_rename_base_name = bpy.props.StringProperty(name="Base Rename Name", default="TypeName")
    # scene-level default starting model id
    bpy.types.Scene.gtass_model_id = bpy.props.IntProperty(name="Start Model ID", default=4542, min=0)

def unregister():
    del bpy.types.Object.ide_flags
    del bpy.types.Object.dff
    del bpy.types.Scene.batch_txd_name
    del bpy.types.Scene.batch_rename_base_name
    del bpy.types.Scene.gtass_model_id
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == '__main__':
    register()

