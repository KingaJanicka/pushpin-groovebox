import glob from 'glob'
import jsonschema from 'jsonschema'
import { cwd } from 'process'
import path from 'path'

const old = glob.sync(path.resolve(path.join(cwd(), '..', 'instr')))