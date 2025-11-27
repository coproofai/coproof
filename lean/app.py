import os
import subprocess
import tempfile
import json
import re
import hashlib
import time
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'lean'}

def isAllowedFile(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def findLeanExecutable():
    possibleCommands = ['lean', 'lean.exe']
    
    for cmd in possibleCommands:
        try:
            result = subprocess.run(
                [cmd, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    possiblePaths = [
        os.path.expanduser('~/.elan/bin/lean'),
        os.path.expanduser('~/.elan/bin/lean.exe'),
        '/usr/local/elan/bin/lean',
        '/usr/local/elan/bin/lean.exe'
    ]
    
    for path in possiblePaths:
        if os.path.exists(path):
            return path
    
    return None

def parseTheoremInfo(leanCode, leanOutput):
    theorems = []
    lines = leanCode.split('\n')
    
    theoremPattern = re.compile(r'^\s*(theorem|def|lemma|example)\s+(\w+)')
    
    for i, line in enumerate(lines, 1):
        match = theoremPattern.match(line)
        if match:
            theoremType = match.group(1)
            theoremName = match.group(2)
            theorems.append({
                'name': theoremName,
                'type': theoremType,
                'line': i,
                'column': match.start(2) + 1
            })
    
    return theorems

def parseLeanMessages(stdout, stderr, filename='proof.lean'):
    messages = []
    
    errorPattern = re.compile(r'([^:]+):(\d+):(\d+):\s*(error|warning|info):\s*(.*?)(?=\n[^\s]|\Z)', re.DOTALL)
    
    combinedOutput = stderr + '\n' + stdout
    
    for match in errorPattern.finditer(combinedOutput):
        file = match.group(1).strip()
        line = int(match.group(2))
        column = int(match.group(3))
        severity = match.group(4)
        message = match.group(5).strip()
        
        messages.append({
            'file': filename,
            'line': line,
            'column': column,
            'severity': severity,
            'message': message
        })
    
    return messages

def extractTheoremDetails(leanCode, leanOutput, filename='proof.lean'):
    theorems = parseTheoremInfo(leanCode, leanOutput)
    messages = parseLeanMessages(leanOutput, leanOutput, filename)
    
    theoremsWithDetails = []
    
    for theorem in theorems:
        theoremMessages = [
            msg for msg in messages 
            if msg['line'] == theorem['line']
        ]
        
        location = f"{filename}:{theorem['line']}:{theorem['column']}"
        
        theoremDetail = {
            'name': theorem['name'],
            'type': theorem['type'],
            'location': location,
            'line': theorem['line'],
            'column': theorem['column'],
            'messages': theoremMessages
        }
        
        theoremsWithDetails.append(theoremDetail)
    
    return theoremsWithDetails

def verifyLeanProof(leanCode, filename='proof.lean'):
    startTime = time.time()
    leanExecutable = findLeanExecutable()
    
    if not leanExecutable:
        endTime = time.time()
        return {
            'verified': False,
            'returnCode': -1,
            'theorems': [],
            'messages': [{
                'file': filename,
                'line': 0,
                'column': 0,
                'severity': 'error',
                'message': 'Lean executable not found. Please install Lean 4 via elan.'
            }],
            'feedback': {
                'stdout': '',
                'stderr': 'Lean executable not found. Please install Lean 4 via elan.'
            },
            'processingTimeSeconds': round(endTime - startTime, 3)
        }
    
    timestamp = str(time.time()).encode('utf-8')
    codeHash = hashlib.sha256(leanCode.encode('utf-8') + timestamp).hexdigest()[:16]
    baseFilename = filename.rsplit('.', 1)[0] if '.' in filename else filename
    hashedFilename = f"{baseFilename}_{codeHash}.lean"
    
    with tempfile.TemporaryDirectory() as tempDir:
        leanFilePath = os.path.join(tempDir, hashedFilename)
        
        with open(leanFilePath, 'w', encoding='utf-8') as f:
            f.write(leanCode)
        
        try:
            result = subprocess.run(
                [leanExecutable, leanFilePath],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=tempDir
            )
            
            verified = result.returncode == 0
            endTime = time.time()
            
            allMessages = parseLeanMessages(result.stdout, result.stderr, hashedFilename)
            
            theorems = parseTheoremInfo(leanCode, result.stdout + result.stderr)
            theoremsWithDetails = []
            
            for theorem in theorems:
                theoremMessages = [
                    msg for msg in allMessages 
                    if msg['line'] == theorem['line']
                ]
                
                location = f"{hashedFilename}:{theorem['line']}:{theorem['column']}"
                
                theoremsWithDetails.append({
                    'name': theorem['name'],
                    'type': theorem['type'],
                    'location': location,
                    'line': theorem['line'],
                    'column': theorem['column'],
                    'messages': theoremMessages
                })
            
            return {
                'verified': verified,
                'returnCode': result.returncode,
                'theorems': theoremsWithDetails,
                'messages': allMessages,
                'feedback': {
                    'stdout': result.stdout.strip(),
                    'stderr': result.stderr.strip()
                },
                'processingTimeSeconds': round(endTime - startTime, 3)
            }
            
        except subprocess.TimeoutExpired:
            endTime = time.time()
            return {
                'verified': False,
                'returnCode': -1,
                'theorems': [],
                'messages': [{
                    'file': filename,
                    'line': 0,
                    'column': 0,
                    'severity': 'error',
                    'message': 'Verification timeout after 60 seconds'
                }],
                'feedback': {
                    'stdout': '',
                    'stderr': 'Verification timeout after 60 seconds'
                },
                'processingTimeSeconds': round(endTime - startTime, 3)
            }
        except FileNotFoundError as e:
            endTime = time.time()
            return {
                'verified': False,
                'returnCode': -1,
                'theorems': [],
                'messages': [{
                    'file': filename,
                    'line': 0,
                    'column': 0,
                    'severity': 'error',
                    'message': f'Lean executable not found: {str(e)}'
                }],
                'feedback': {
                    'stdout': '',
                    'stderr': f'Lean executable not found: {str(e)}'
                },
                'processingTimeSeconds': round(endTime - startTime, 3)
            }
        except Exception as e:
            endTime = time.time()
            return {
                'verified': False,
                'returnCode': -1,
                'theorems': [],
                'messages': [{
                    'file': filename,
                    'line': 0,
                    'column': 0,
                    'severity': 'error',
                    'message': str(e)
                }],
                'feedback': {
                    'stdout': '',
                    'stderr': str(e)
                },
                'processingTimeSeconds': round(endTime - startTime, 3)
            }

@app.route('/health', methods=['GET'])
def healthCheck():
    return jsonify({'status': 'healthy'}), 200

@app.route('/verify', methods=['POST'])
def verifyProof():
    try:
        leanCode = None
        filename = 'proof.lean'
        
        if request.is_json:
            data = request.get_json()
            leanCode = data.get('code')
            filename = data.get('filename', 'proof.lean')
            
            if not leanCode:
                return jsonify({
                    'error': 'No code provided in JSON body',
                    'verified': False
                }), 400
                
        elif request.content_type and 'text/plain' in request.content_type:
            leanCode = request.data.decode('utf-8')
            filename = request.args.get('filename', 'proof.lean')
            
            if not leanCode:
                return jsonify({
                    'error': 'No code provided in request body',
                    'verified': False
                }), 400
                
        elif 'file' in request.files:
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({
                    'error': 'No file selected',
                    'verified': False
                }), 400
            
            if not isAllowedFile(file.filename):
                return jsonify({
                    'error': 'Invalid file type. Only .lean files are allowed',
                    'verified': False
                }), 400
            
            leanCode = file.read().decode('utf-8')
            filename = secure_filename(file.filename)
        else:
            return jsonify({
                'error': 'No code provided. Send JSON with "code" field, plain text body, or multipart file upload',
                'verified': False
            }), 400
        
        result = verifyLeanProof(leanCode, filename)
        statusCode = 200 if result['verified'] else 422
        
        return jsonify(result), statusCode
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to process request: {str(e)}',
            'verified': False,
            'theorems': [],
            'messages': []
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
