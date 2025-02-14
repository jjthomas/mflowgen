#! /usr/bin/env python
#=========================================================================
# Step.py
#=========================================================================
#
# Author : Christopher Torng
# Date   : June 2, 2019
#

import copy
import os
import yaml

from ..utils import get_top_dir

class Step ( object ):

  def __init__( s, step_path, default=False ):

    # Get the YAML file path
    #
    # If this is a default step, then we use the top-level steps directory

    s._config = {}

    if default:
      yaml_path = '/'.join([
        get_top_dir(),
        'steps',
        step_path,
        'configure.yml'
      ])
    else:
      yaml_path = '/'.join([
        step_path,
        'configure.yml'
      ])

    # Read the YAML data

    with open( yaml_path, 'r' ) as fd:
      try:
        data = yaml.load( fd, Loader=yaml.FullLoader )
      except AttributeError:
        # PyYAML for python2 does not have FullLoader
        data = yaml.load( fd )

    # Check that this is a valid step configuration

    assert 'name' in data.keys(), \
      'Step -- ' \
      'Step YAML must have a "name" field: {}'.format( yaml_path )

    # Remove empty inputs and outputs

    if 'inputs' in data.keys():
      if not data['inputs']:
        del( data['inputs'] )

    if 'outputs' in data.keys():
      if not data['outputs']:
        del( data['outputs'] )

    # Check that any tagged outputs only have one key and one value

    if 'outputs' in data.keys():
      for idx, o in enumerate( data['outputs'] ):
        if type(o) == dict:
          assert len( o.keys()   ) == 1, 'Step -- Invalid output'
          assert len( o.values() ) == 1, 'Step -- Invalid output'

    # If commands are empty, replace with 'pass'

    if 'commands' not in data.keys():
      data['commands'] = [ 'true' ]

    if 'commands' in data.keys():
      if data['commands'] == [] or data['commands'] == None:
        data['commands'] = [ 'true' ]

    # Make sure we read the commands as strings
    #
    # - A shell command of 'true' mistakenly turns into a python boolean,
    #   so convert it back into a (lowercase) string..
    #

    assert type( data['commands'] ) == list, \
      'Step -- YAML "commands" must be a list: {}'.format( yaml_path )

    for i, c in enumerate( data['commands'] ):
      if type( c ) == bool:
        data['commands'][i] = str(c).lower()

    # Replace any output tag shorthands with the real files
    #
    # So this configuration YAML:
    #
    #     outputs:
    #     - foo1.txt
    #     - foo2.txt
    #     - ~: results/1/2/3/data.txt
    #
    # Turns into this:
    #
    #     outputs = [
    #     - foo1.txt
    #     - foo2.txt
    #     - data.txt: results/1/2/3/data.txt
    #     ]
    #

    if 'outputs' in data.keys():
      for idx, o in enumerate( data['outputs'] ):
        if type(o) == dict:
          if o.keys()[0] == None:
            f = o.values()[0]
            data['outputs'][idx] = { os.path.basename( f ) : f }

    # Save the config

    s._config.update( data )

    # Save additional metadata aside from the YAML data
    #
    # - Step directory -- we copy this when we instance a step in a build
    # - YAML name      -- used to generate a parameterized YAML in a build
    #

    s.step_dir = \
      os.path.relpath( os.path.dirname( yaml_path ), os.getcwd() )

    s.yaml_name = os.path.basename( yaml_path )

  #-----------------------------------------------------------------------
  # Clone
  #-----------------------------------------------------------------------

  def clone( s ):
    new_step = Step.__new__( Step )
    new_step._config = copy.deepcopy( s._config )
    new_step.step_dir  = s.step_dir
    new_step.yaml_name = s.yaml_name
    return new_step

  #-----------------------------------------------------------------------
  # API to help build graphs interactively
  #-----------------------------------------------------------------------

  # Get handles (that can be connected with Graph .connect)

  def get_input_handle( s, f ):

    assert s._config['inputs'], \
      'get_input_handle -- This step has no inputs'
    assert f in s._config['inputs'], \
      'get_input_handle -- No input "%s" found in the step' % f

    handle = ( s._config['name'], 'inputs', f )

    return handle

  def get_output_handle( s, f ):

    assert s._config['outputs'], \
      'get_output_handle -- This step has no outputs'

    outputs = s.all_outputs()

    assert f in outputs, \
      'get_output_handle -- No output "%s" found in the step' % f

    handle = ( s._config['name'], 'outputs', f )

    return handle

  # Syntactic sugar for getting input and output handles

  def i( s, name ):
    return s.get_input_handle( name )

  def o( s, name ):
    return s.get_output_handle( name )

  # All handles at once to make it easy to connect between steps by name

  def all_input_handles( s ):
    if 'inputs' not in s._config.keys():
      return []
    input_handles = \
      [ s.get_input_handle( name ) for name in s._config['inputs'] ]
    return input_handles

  def all_output_handles( s ):
    if 'outputs' not in s._config.keys():
      return []
    outputs = s.all_outputs()
    output_handles = \
      [ s.get_output_handle( name ) for name in outputs ]
    return output_handles

  #-----------------------------------------------------------------------
  # Parameter system
  #-----------------------------------------------------------------------

  def set_name( s, name ):
    s._config['name'] = name

  def get_name( s ):
    return s._config['name']

  def set_param( s, param, value ):
    assert 'parameters' in s._config.keys(), \
      'set_param -- ' \
      'No parameter "%s" in step "%s"' % ( param, s.get_name() )
    assert param in s._config['parameters'].keys(), \
      'set_param -- ' \
      'No parameter "%s" in step "%s" (options: %s)' % \
        ( param, s.get_name(), s._config['parameters'].keys() )
    s._config['parameters'][param] = value

  def get_param( s, param ):
    assert 'parameters' in s._config.keys(), \
      'get_param -- ' \
      'No parameter "%s" in step "%s"' % ( param, s.get_name() )
    assert param in s._config['parameters'].keys(), \
      'get_param -- ' \
      'No parameter "%s" in step "%s" (options: %s)' % \
        ( param, s.get_name(), s._config['parameters'].keys() )
    return s._config['parameters'][param]

  def update_params( s, params ):
    assert type(params) == dict, \
      'update_param -- ' \
      'Expecting argument of type dictionary to update parameters'
    # Only update parameters that were defined in the configuration YAML
    try:
      for p in params.keys():
        if p in s._config['parameters'].keys():
          s._config['parameters'][p] = params[p]
    except KeyError:
      pass

  def params( s ):
    if 'parameters' not in s._config.keys():
      return {}
    return s._config['parameters']

  # expand_params
  #
  # Populate all parameters in outputs and commands

  def expand_params( s ):

    # Expand outputs

    if 'outputs' in s._config.keys():
      for idx, o in enumerate( s._config['outputs'] ):
        if type(o) == dict:
          key   = o.keys()[0].format( **s.params() )
          value = o.values()[0].format( **s.params() )
          s._config['outputs'][idx] = { key : value }
        elif type(o) == str:
          output = o.format( **s.params() )
          s._config['outputs'][idx] = output
        else:
          assert False, \
            'expand_params -- ' \
            'Unrecognized type %s in output "%s"' % ( type(o), o )

    # Expand commands

    if 'commands' in s._config.keys():
      for idx, c in enumerate( s._config['commands'] ):
        try:
          s._config['commands'][idx] = c.format( **s.params() )
        except KeyError as e:
          cause = e.args[0]
          raise KeyError( 'Error: Unrecognized parameter "' + cause + '"'
            ' in commands for step "' + s.get_name() + '"!' +
            ' Please escape literal curly braces with double braces' )

    # Expand debug

    if 'debug' in s._config.keys():
      for idx, c in enumerate( s._config['debug'] ):
        s._config['debug'][idx] = c.format( **s.params() )

  #-----------------------------------------------------------------------
  # Ninja helpers
  #-----------------------------------------------------------------------

  # escape_dollars
  #
  # Ninja expects dollar signs to be escaped

  def escape_dollars( s ):

    # Escape outputs

    if 'outputs' in s._config.keys():
      for idx, o in enumerate( s._config['outputs'] ):
        if type(o) == dict:
          key   = o.keys()[0].replace( '$', '$$' )
          value = o.values()[0].replace( '$', '$$' )
          s._config['outputs'][idx] = { key : value }
        elif type(o) == str:
          output = o.replace( '$', '$$' )
          s._config['outputs'][idx] = output
        else:
          assert False, \
            'escape_dollars -- ' \
            'Unrecognized type %s in output "%s"' % ( type(o), o )

    # Escape commands

    if 'commands' in s._config.keys():
      for idx, c in enumerate( s._config['commands'] ):
        s._config['commands'][idx] = c.replace( '$', '$$' )

    # Escape debug

    if 'debug' in s._config.keys():
      for idx, c in enumerate( s._config['debug'] ):
        s._config['debug'][idx] = c.replace( '$', '$$' )

  #-----------------------------------------------------------------------
  # Observability methods
  #-----------------------------------------------------------------------

  # List all inputs

  def all_inputs( s ):
    if 'inputs' not in s._config.keys():
      return []
    return s._config['inputs']

  # all_outputs -- normal version
  #
  # This is the list of all outputs that appear in the 'outputs/' dir
  #
  # Unpack tagged outputs such that this configuration YAML:
  #
  #     outputs:
  #     - foo1.txt
  #     - foo2.txt
  #     - foo3.txt: results/1/2/3/data.txt
  #
  # Turns into this:
  #
  #     outputs = [
  #       'foo1.txt',
  #       'foo2.txt',
  #       'foo3.txt',
  #     ]
  #

  def all_outputs( s ):
    if 'outputs' not in s._config.keys():
      return []
    outputs = list( s._config['outputs'] )
    for idx, o in enumerate( outputs ):
      if type(o) == dict:
        outputs[idx] = o.keys()[0]
    return outputs

  # all_outputs_execute -- execute version
  #
  # This is the list of all outputs that 'execute' will generate.
  #
  # Unpack tagged outputs such that this configuration YAML:
  #
  #     outputs:
  #     - foo1.txt
  #     - foo2.txt
  #     - foo3.txt: results/1/2/3/data.txt
  #
  # Turns into this:
  #
  #     outputs = [
  #       'foo1.txt',
  #       'foo2.txt',
  #       '../results/1/2/3/data.txt',  <-- relative to 'outputs/' dir
  #     ]
  #

  def all_outputs_execute( s ):
    if 'outputs' not in s._config.keys():
      return []
    outputs = list( s._config['outputs'] )
    for idx, o in enumerate( outputs ):
      if type(o) == dict:
        outputs[idx] = '../' + o.values()[0]
    return outputs

  # all_outputs_tagged -- version with only the tagged subset
  #
  # These are the outputs that need to be linked to the 'outputs/' dir.
  #
  # Return only tagged outputs so that this configuration YAML:
  #
  #     outputs:
  #     - foo1.txt
  #     - foo2.txt
  #     - foo3.txt: results/1/2/3/data.txt
  #
  # Returns this:
  #
  #     outputs = [
  #       { foo3.txt: results/1/2/3/data.txt }
  #     ]
  #

  def all_outputs_tagged( s ):
    if 'outputs' not in s._config.keys():
      return []
    return [ o for o in s._config['outputs'] if type(o) == dict ]

  # all_outputs_untagged -- version with only the untagged subset
  #
  # These are the outputs that need to be stamped in the 'outputs/' dir.
  #
  # Return only untagged outputs so that this configuration YAML:
  #
  #     outputs:
  #     - foo1.txt
  #     - foo2.txt
  #     - foo3.txt: results/1/2/3/data.txt
  #
  # Returns this:
  #
  #     outputs = [
  #       'foo1.txt',
  #       'foo2.txt',
  #     ]
  #

  def all_outputs_untagged( s ):
    if 'outputs' not in s._config.keys():
      return []
    return [ o for o in s._config['outputs'] if type(o) != dict ]

  #-----------------------------------------------------------------------
  # Used in backends
  #-----------------------------------------------------------------------

  def get_dir( s ):
    return s.step_dir

  def get_commands( s ):
    return s._config['commands']

  def get_debug_commands( s ):
    if 'debug' in s._config.keys():
      return s._config['debug']
    else:
      return []

  def dump_yaml( s, build_dir ):
    with open( build_dir + '/' + s.yaml_name, 'w' ) as fd:
      yaml.dump( s._config, fd, default_flow_style=False )

  # The sandbox flag will copy the source step directory if true (default)
  # or symlink the source files into the build directory if false

  def set_sandbox( s, val ):
    s._config['sandbox'] = val

  def get_sandbox( s ):
    try:
      return s._config['sandbox']
    except KeyError:
      return True


