#! /usr/bin/env python
#=========================================================================
# BuildOrchestrator.py
#=========================================================================
# Backend that generates ninja build files from a graph
#
# Author : Christopher Torng
# Date   : June 11, 2019
#

import os
import shutil

from .utils import *

class BuildOrchestrator( object ):

  def __init__( s, graph, backend_writer_cls ):

    s.g = graph
    s.w = backend_writer_cls()

    # The 'build' method analyzes the user's step dependency graph in
    # order to populate the rules and high-level dependencies (e.g., this
    # step depends on that step) of the build system graph

    s.build_system_rules = {}
    s.build_system_deps  = {}

    # Build order

    s.order = []

    # Metadata for each build directory

    s.build_dirs = {}
    s.build_ids  = {}
    s.step_dirs  = {}

    # Hidden metadata directory that saves parameterized YAMLs and
    # commands for each step

    s.metadata_dir = '.mflowgen'

    if os.path.exists( s.metadata_dir ):
      shutil.rmtree( s.metadata_dir )

    os.mkdir( s.metadata_dir )

  #-----------------------------------------------------------------------
  # dump_yamls
  #-----------------------------------------------------------------------
  # For the parameter system, we will dump each step's (parameterized)
  # configuration data into a hidden metadata directory.
  #

  def dump_yamls( s, step_name, build_dir ):
    inner_dir = s.metadata_dir + '/' + build_dir
    if not os.path.exists( inner_dir ):
      os.mkdir( inner_dir )
    step = s.g.get_step( step_name )
    step.dump_yaml( inner_dir )

  #-----------------------------------------------------------------------
  # dump_commands
  #-----------------------------------------------------------------------
  # Each step's command script goes into the hidden metadata directory.
  # When executing a step, we just copy the commands to the build dir and
  # run it there. This also makes it easy for the user to run the step in
  # isolation for debug purposes.
  #

  def dump_commands( s, commands, step_name, build_dir ):

    # Directories

    inner_dir = s.metadata_dir + '/' + build_dir
    if not os.path.exists( inner_dir ):
      os.mkdir( inner_dir )

    # Generate the command script

    gen = os.path.abspath( __file__ ).rstrip('c')

    with open( inner_dir + '/mflowgen-run.sh', 'w' ) as fd:

      # Header

      fd.write( '#' + '='*73 + '\n' )
      fd.write( '# mflowgen-run.sh\n' )
      fd.write( '#' + '='*73 + '\n' )
      fd.write( '# Generator : ' + gen + '\n' )
      fd.write( '\n' )

      # Pre
      #
      # - Starting timestamp
      # - Dump all parameters into the script
      #

      params          = s.g.get_step( step_name ).params()
      params_str      = 'export {}={}'
      params_commands = \
        [ params_str.format(k,v) for k, v in params.items() ]

      pre = [
        'date +%Y-%m%d-%H%M-%S > .time_start', # starting timestamp
      ]

      pre = pre + params_commands

      fd.write( '# Pre\n' )
      fd.write( '\n' )
      for c in pre:
        fd.write( c )
        fd.write( '\n' )
      fd.write( '\n' )

      # Commands

      fd.write( '# Commands\n' )
      fd.write( '\n' )
      fd.write( '(\n' )
      for c in commands:
        fd.write( c )
        fd.write( '\n' )
      fd.write( ')\n' )
      fd.write( '\n' )

      # Post
      #
      # - Ending timestamp
      #

      post = [
        'date +%Y-%m%d-%H%M-%S > .time_end', # ending timestamp
      ]

      fd.write( '# Post\n' )
      fd.write( '\n' )
      for c in post:
        fd.write( c )
        fd.write( '\n' )
      fd.write( '\n' )

  #-----------------------------------------------------------------------
  # dump_debug_commands
  #-----------------------------------------------------------------------
  # Each step's debug command script goes into the hidden metadata
  # directory. When executing debug for a step, we just copy the commands
  # to the build dir and run it there. This also makes it easy for the
  # user to launch debug on their own.
  #

  def dump_debug_commands( s, commands, step_name, build_dir ):

    # Directories

    inner_dir = s.metadata_dir + '/' + build_dir
    if not os.path.exists( inner_dir ):
      os.mkdir( inner_dir )

    # Generate the debug command script

    gen = os.path.abspath( __file__ ).rstrip('c')

    with open( inner_dir + '/mflowgen-debug.sh', 'w' ) as fd:

      # Header

      fd.write( '#' + '='*73 + '\n' )
      fd.write( '# mflowgen-debug.sh\n' )
      fd.write( '#' + '='*73 + '\n' )
      fd.write( '# Generator : ' + gen + '\n' )
      fd.write( '\n' )

      # Params

      params          = s.g.get_step( step_name ).params()
      params_str      = 'export {}={}'
      params_commands = \
        [ params_str.format(k,v) for k, v in params.items() ]

      fd.write( '# Pre\n' )
      fd.write( '\n' )
      for c in params_commands:
        fd.write( c )
        fd.write( '\n' )
      fd.write( '\n' )

      # Commands

      fd.write( '# Debug\n' )
      fd.write( '\n' )
      for c in commands:
        fd.write( c )
        fd.write( '\n' )
      fd.write( '\n' )

  #-----------------------------------------------------------------------
  # dump_graphviz
  #-----------------------------------------------------------------------
  # Dump the graphviz dot file that visualizes the user-defined graph into
  # the hidden metadata directory.
  #
  # Note that this is not the build system graph, which is likely too
  # detailed to understand much from.
  #

  def dump_graphviz( s ):
    s.g.plot( dot_f = s.metadata_dir + '/graph.dot' )

  #---------------------------------------------------------------------
  # Setup
  #---------------------------------------------------------------------

  def setup( s ):

    # Check the validity of this graph (no cycles)

    #assert s.g.check_cycles() == None

    # Expand parameters in the graph

    s.g.expand_params()

    # Determine build order, unique build directories, build IDs, step dir

    s.order = s.g.topological_sort()

    for i, step_name in enumerate( s.order ):
      s.build_dirs [ step_name ] = str(i) + '-' + step_name
      s.build_ids  [ step_name ] = str(i)
      s.step_dirs  [ step_name ] = s.g.get_step( step_name ).get_dir()

    # Dump parameterized YAMLs for each step to the metadata directory

    for step_name, build_dir in s.build_dirs.items():
      s.dump_yamls( step_name, build_dir )

    # Dump commands for each step to the metadata directory

    for step_name, build_dir in s.build_dirs.items():
      step          = s.g.get_step( step_name )
      step_commands = step.get_commands()
      if step_commands:
        s.dump_commands( step_commands, step_name, build_dir )

    # Dump debug commands for each step to the metadata directory

    for step_name, build_dir in s.build_dirs.items():
      step           = s.g.get_step( step_name )
      debug_commands = step.get_debug_commands()
      if debug_commands:
        s.dump_debug_commands( debug_commands, step_name, build_dir )

    # Dump graphviz dot file to the metadata directory

    s.dump_graphviz()

  #-----------------------------------------------------------------------
  # build
  #-----------------------------------------------------------------------
  # Turn the user-level step dependency graph into a build system
  # dependency graph and use the backend writer interface to generate the
  # build file. For each step in the graph, we create the following
  # targets:
  #
  # - directory       -- Create build dir by copying the step template
  # - collect-inputs  -- Collect dependencies into the 'inputs/' dir
  # - execute         -- Run any commands for the step
  # - collect-outputs -- Collect tagged outputs into the 'outputs/' dir
  # - alias           -- Define an alias for this step (i.e., step name)
  #
  # They are arranged with the following dependencies:
  #
  #     +-----------+
  #     | directory |
  #     +-----------+
  #      |     |
  #      |     v
  #      |   +----------------+
  #      |   | collect-inputs |
  #      |   +----------------+
  #      |       |
  #      v       v
  #     +---------+
  #     | execute |
  #     +---------+
  #      |       |
  #      |       v
  #      |   +-----------------+
  #      |   | collect-outputs |
  #      |   +-----------------+
  #      |     |
  #      v     v
  #     +-------+
  #     | alias |
  #     +-------+
  #
  # These two extra edges allow steps to run even if they do not have any
  # inputs or outputs (e.g., analysis-only steps).
  #
  # - 'directory' -> 'execute'
  # - 'execute'   -> 'alias'
  #
  #---------------------------------------------------------------------
  # Additional notes on customized backends
  #---------------------------------------------------------------------
  # Using this method and a backend writer interface works for most use
  # cases.
  #
  # For more customization (e.g., comments, formatting, any additional
  # rules not easily hooked in here), we also keep track of two variables:
  #
  # - s.build_system_rules  <- access this via s.get_all_rules()
  # - s.build_system_deps   <- access this via s.get_all_deps()
  #
  # A backend writer can use these variables to customize the output
  # much more flexibly, but it is also much more complicated!
  #
  # The data is organized like this:
  #
  #     s.build_system_rules[ 'step1' ] = {
  #         'directory'       : { ... kwargs to create directory ... },
  #         'collect-inputs'  : { ... kwargs to collect inputs   ... },
  #         'execute'         : { ... kwargs to execute commands ... },
  #         'collect-outputs' : { ... kwargs to collect outputs  ... },
  #         'alias'           : { ... kwargs to create alias     ... },
  #     }
  #
  # The high-level build system dependencies are also captured. So for
  # example, 'step1' can create its directory only when previous dependent
  # 'step0' has finished creating an alias. The backend build system is in
  # charge of taking whatever the target is (e.g., stamp files) and adding
  # it to the dependencies list according to this high-level information.
  #
  #     s.build_system_deps[ 'step1' ] = {
  #         'directory'       : [ ( 'step0', 'alias'           ) ]
  #         'collect-inputs'  : [ ( 'step1', 'directory'       ) ]
  #         'execute'         : [ ( 'step1', 'collect-inputs'  ) ],
  #         'collect-outputs' : [ ( 'step1', 'execute'         ) ],
  #         'alias'           : [ ( 'step1', 'collect-outputs' ) ],
  #     }
  #

  def build( s ):

    # Setup

    s.setup()

    # Pass useful data to the backend writer

    s.w.save( s.order, s.build_dirs, s.step_dirs )

    # Backend writer prologue

    s.w.gen_header()
    s.w.gen_prologue()

    # Keep track of build-system-specific dependency trackers

    backend_outputs = {}

    # Loop over all steps in topological order

    for i, step_name in enumerate( s.order ):

      step      = s.g.get_step( step_name )
      build_dir = s.build_dirs[ step_name ]
      build_id  = s.build_ids[ step_name ]

      s.build_system_rules[ step_name ] = {}
      s.build_system_deps[ step_name ]  = {}

      backend_outputs[ step_name ] = {}

      # Use the backend writer to generate the step header

      s.w.gen_step_header( step_name )

      #...................................................................
      # directory
      #...................................................................

      s.w.gen_step_directory_pre()

      # Make the directory dependent on all source files

      step_template_dir = s.step_dirs[ step_name ]
      deps              = []
      #deps              = get_files_in_dir( step_template_dir )

      # Remove any broken symlinks from the dependency list

      deps_filtered = []
      for f in deps:
        try:
          os.stat( f )
          deps_filtered.append( f )
        except OSError as e:
          pass
      deps = deps_filtered

      # Check if we are going to sandbox this step or symlink it

      sandbox = step.get_sandbox()

      # Rule
      #
      # - Remove the {dst}
      # - Copy the {src} to the {dst}
      # - This rule depends on {deps}
      # - {sandbox} True (copies src dir), False (symlinks src contents)
      #

      rule = {
        'dst'     : build_dir,
        'src'     : step_template_dir,
        'deps'    : deps,
        'sandbox' : sandbox,
      }

      # Pull in any backend dependencies

      extra_deps = set()

      for edge in s.g.get_edges_i( step_name ):
        src_step_name, src_f = edge.get_src()
        for o in backend_outputs[src_step_name]['alias']:
          extra_deps.add( o )

      extra_deps = list( extra_deps )

      # Use the backend writer to generate the rule, and then grab any
      # backend dependencies

      t = s.w.gen_step_directory( extra_deps = extra_deps, **rule )

      backend_outputs[step_name]['directory'] = t

      # Metadata for customized backends

      s.build_system_rules[step_name]['directory'] = rule

      s.build_system_deps[step_name]['directory'] = set()

      for edge in s.g.get_edges_i( step_name ):
        src_step_name, src_f = edge.get_src()
        s.build_system_deps[step_name]['directory'].add(
          ( src_step_name, 'alias' )
        )

      #...................................................................
      # collect-inputs
      #...................................................................
      # For each incoming edge, trace back and collect the input (i.e.,
      # symlink the src step's output to this step's input).

      s.w.gen_step_collect_inputs_pre()

      # Pull in any backend dependencies

      extra_deps = backend_outputs[step_name]['directory']

      # Metadata for customized backends

      s.build_system_rules[step_name]['collect-inputs'] = []

      # Use the backend writer to generate rules for each input, and then
      # grab any backend dependencies

      backend_outputs[step_name]['collect-inputs'] = []

      for edge in s.g.get_edges_i( step_name ):

        src_step_name, src_f = edge.get_src()
        dst_step_name, dst_f = edge.get_dst()

        link_src = s.build_dirs[ src_step_name ] + '/outputs/' + src_f
        link_dst = s.build_dirs[ dst_step_name ] + '/inputs/'  + dst_f

        # Rule
        #
        # - Symlink the {src} to the {dst}
        # - This rule depends on {deps}
        #

        rule = {
          'dst'  : link_dst,
          'src'  : link_src,
          'deps' : [],
        }

        t = s.w.gen_step_collect_inputs( extra_deps = extra_deps, **rule )

        backend_outputs[step_name]['collect-inputs'] += t

        s.build_system_rules[step_name]['collect-inputs'].append( rule )

      # Metadata for customized backends

      s.build_system_deps[step_name]['collect-inputs'] = set()

      s.build_system_deps[step_name]['collect-inputs'].add(
        ( step_name, 'directory' )
      )

      #...................................................................
      # execute
      #...................................................................
      # Executing the step just involves running the commands script saved
      # in the hidden metadata directory.

      s.w.gen_step_execute_pre()

      # Outputs and commands

      outputs = [ build_dir + '/outputs/' + f \
                    for f in step.all_outputs_execute() ]

      if not outputs:
        outputs = [ build_dir + '/execute-phony' ]
        phony   = True
      else:
        phony   = False

      commands = ' && '.join([
        # Step banner in big letters
        'python ' + get_top_dir() + '/utils/letters.py -c -t ' + step_name,
        # Copy the command script to the build_dir
        'cp -f ' + s.metadata_dir + '/' + build_dir \
                 + '/mflowgen-run.sh ' + build_dir,
        'cd ' + build_dir,
        # Run the commands
        'sh mflowgen-run.sh 2>&1 | tee mflowgen-run.log',
        # Return to top so backends can assume we never changed directory
        'cd ..',
      ])

      # Rule
      #
      # - Run the {command}
      # - Generate the {outputs}
      # - This rule depends on {deps}
      #

      rule = {
        'outputs' : outputs,
        'command' : commands,
        'deps'    : [],
        'phony'   : phony,
      }

      # Pull in any backend dependencies

      extra_deps = set()

      for o in backend_outputs[step_name]['directory']:
        extra_deps.add( o )
      for o in backend_outputs[step_name]['collect-inputs']:
        extra_deps.add( o )

      extra_deps = list( extra_deps )

      # Use the backend writer to generate the rule, and then grab any
      # backend dependencies

      t = s.w.gen_step_execute( extra_deps = extra_deps, **rule )

      backend_outputs[step_name]['execute'] = t

      # Metadata for customized backends

      s.build_system_rules[step_name]['execute'] = rule

      s.build_system_deps[step_name]['execute'] = set()

      s.build_system_deps[step_name]['execute'].add(
        ( step_name, 'directory' )
      )

      s.build_system_deps[step_name]['execute'].add(
        ( step_name, 'collect-inputs' )
      )

      #...................................................................
      # collect-outputs
      #...................................................................
      # Outputs may be tagged or untagged in the YAML configuration:
      #
      #     outputs:
      #       - file1.txt : path/to/the/data.txt     <-- tagged
      #       - file2.txt                            <-- untagged
      #
      # Tagged outputs need to be symlinked to the 'outputs' directory.
      # Untagged outputs are assumed to be already in the 'outputs'
      # directory.
      #
      # Some backend build systems may need to process the untagged
      # outputs to build dependency edges (e.g., timestamping), so in this
      # section we collect rules for both tagged and untagged outputs.

      s.w.gen_step_collect_outputs_pre()

      # Pull in any backend dependencies

      extra_deps = backend_outputs[step_name]['execute']

      # Metadata for customized backends

      s.build_system_rules[step_name]['collect-outputs'] = { \
        'tagged'   : [],
        'untagged' : [],
      }

      # Use the backend writer to generate rules for each tagged output,
      # and then grab any backend dependencies

      backend_outputs[step_name]['collect-outputs'] = []

      for o in step.all_outputs_tagged():

        link_src = build_dir + '/' + o.values()[0]
        link_dst = build_dir + '/outputs/' + o.keys()[0]

        # Rule
        #
        # - Symlink the {src} to the {dst}
        # - This rule depends on {deps}
        #

        rule = {
          'dst'  : link_dst,
          'src'  : link_src,
          'deps' : [],
        }

        t = s.w.gen_step_collect_outputs_tagged(
          extra_deps=extra_deps, **rule
        )

        backend_outputs[step_name]['collect-outputs'] += t

        d = s.build_system_rules[step_name]['collect-outputs']
        d['tagged'].append( rule )

      # Do whatever is necessary to the untagged outputs

      for o in step.all_outputs_untagged():

        f = build_dir + '/outputs/' + o

        # Rule
        #
        # - Do whatever is necessary to the untagged output {f}
        # - This rule depends on {deps}
        #

        rule = {
          'f'    : f,
          'deps' : [],
        }

        t = s.w.gen_step_collect_outputs_untagged(
          extra_deps=extra_deps, **rule
        )

        backend_outputs[step_name]['collect-outputs'] += t

        d = s.build_system_rules[step_name]['collect-outputs']
        d['untagged'].append( rule )

      # Metadata for customized backends

      s.build_system_deps[step_name]['collect-outputs'] = set()

      s.build_system_deps[step_name]['collect-outputs'].add(
        ( step_name, 'execute' )
      )

      #...................................................................
      # alias
      #...................................................................
      # Here we create nice names for building this entire step

      s.w.gen_step_alias_pre()

      # Pull in any backend dependencies

      extra_deps = set()

      for o in backend_outputs[step_name]['execute']:
        extra_deps.add( o )
      for o in backend_outputs[step_name]['collect-outputs']:
        extra_deps.add( o )

      extra_deps = list( extra_deps )

      # Metadata for customized backends

      s.build_system_rules[step_name]['alias'] = []

      # Use the backend writer to generate rules for each input, and then
      # grab any backend dependencies

      backend_outputs[step_name]['alias'] = []

      # Rule
      #
      # - Create an alias called {alias} for this step
      # - This rule depends on {deps}
      #

      rule = {
        'alias' : step_name,
        'deps' : [],
      }

      t = s.w.gen_step_alias( extra_deps = extra_deps, **rule )
      backend_outputs[step_name]['alias'] += t

      s.build_system_rules[step_name]['alias'].append( rule )

      # Rule
      #
      # - Create an alias called {alias} for this step
      # - This rule depends on {deps}
      #

      rule = {
        'alias' : build_id,
        'deps' : [],
      }

      t = s.w.gen_step_alias( extra_deps = extra_deps, **rule )
      backend_outputs[step_name]['alias'] += t

      s.build_system_rules[step_name]['alias'].append( rule )

      # Metadata for customized backends

      s.build_system_deps[step_name]['alias'] = set()

      s.build_system_deps[step_name]['alias'].add(
        ( step_name, 'execute' )
      )

      s.build_system_deps[step_name]['alias'].add(
        ( step_name, 'collect-outputs' )
      )

      #...................................................................
      # debug
      #...................................................................
      # Generate the debug commands if they are defined in the YAML.

      s.w.gen_step_debug_pre()

      debug_commands = step.get_debug_commands()

      if debug_commands:

        commands = ' && '.join([
          'cp -f ' + s.metadata_dir + '/' + build_dir \
                   + '/mflowgen-debug.sh ' + build_dir,
          'cd ' + build_dir,
          'sh mflowgen-debug.sh 2>&1 | tee mflowgen-debug.log'
        ])

        # Rule
        #
        # - Run the {command}
        # - Generate the {outputs}
        #

        rule = {
          'outputs' : [ 'debug-' + step_name ],
          'command' : commands,
        }

        s.w.gen_step_debug( **rule )

        s.build_system_rules[step_name]['debug'] = [ rule ]

      else:

        s.build_system_rules[step_name]['debug'] = []

    # Now that all steps are done...

    # Call the backend writer's epilogue

    s.w.gen_epilogue()

  #-----------------------------------------------------------------------
  # Backend API
  #-----------------------------------------------------------------------
  # The backend targets a specific build system (e.g., make, ninja) and
  # uses this API to query what commands to generate.

  def get_order( s ):
    return s.order

  def get_build_dir( s, step_name ):
    return s.build_dirs[step_name]

  def get_rules( s, step_name, stage ):
    return s.build_system_rules[step_name][stage]

  def get_deps( s, step_name, stage ):
    return s.build_system_deps[step_name][stage]

  def get_all_rules( s ):
    return s.build_system_rules

  def get_all_deps( s ):
    return s.build_system_deps


