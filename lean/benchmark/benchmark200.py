import json
import time
import requests
import csv
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional

API_URL = "http://localhost:5000/verify"
BENCHMARK_SIZE = 100

theoremCache = {}

def loadBenchmarkData(filePath: str, limit: int = None) -> List[Dict[str, Any]]:
    with open(filePath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, list):
        theorems = data
    else:
        theorems = data.get('data', [])
    
    if limit:
        theorems = theorems[:limit]
    
    return theorems

def fetchTheoremSource(theorem: Dict[str, Any]) -> Optional[str]:
    url = theorem.get('url', '')
    commit = theorem.get('commit', '')
    filePath = theorem.get('file_path', '')
    start = theorem.get('start', [])
    end = theorem.get('end', [])
    fullName = theorem.get('full_name', '')
    
    if fullName in theoremCache:
        return theoremCache[fullName]
    
    if not url or not commit or not filePath or not start or not end:
        return None
    
    rawUrl = f"{url}/raw/{commit}/{filePath}"
    
    try:
        response = requests.get(rawUrl, timeout=10)
        if response.status_code == 200:
            fileContent = response.text
            
            theoremCache[fullName] = fileContent
            return fileContent
    except Exception as e:
        print(f"    Error fetching {fullName}: {e}")
    
    return None

def extractProofState(theorem: Dict[str, Any]) -> str:
    filePath = theorem.get('file_path', '')
    fullName = theorem.get('full_name', 'unknown_theorem')
    
    return {
        'file_path': filePath,
        'full_name': fullName,
        'theorem': theorem
    }

def verifyTheorem(theoremData: Dict[str, Any]) -> Dict[str, Any]:
    fullName = theoremData['full_name']
    theorem = theoremData['theorem']
    
    tacticStates = theorem.get('traced_tactics', [])
    
    fetchStartTime = time.time()
    theoremSource = fetchTheoremSource(theorem)
    fetchEndTime = time.time()
    fetchTime = fetchEndTime - fetchStartTime
    
    if theoremSource:
        leanCode = theoremSource
    else:
        leanCode = f"-- Theorem: {fullName}\nexample : True := by\n  trivial"
    
    try:
        apiStartTime = time.time()
        response = requests.post(
            API_URL,
            json={'code': leanCode, 'filename': f'{fullName}.lean'},
            timeout=35
        )
        apiEndTime = time.time()
        apiLatency = apiEndTime - apiStartTime
        
        if response.status_code in [200, 422]:
            result = response.json()
            return {
                'success': True,
                'verified': result.get('verified', False),
                'fetch_time': fetchTime,
                'api_latency': apiLatency,
                'api_processing_time': result.get('processingTimeSeconds', 0),
                'full_name': fullName,
                'file_path': theoremData.get('file_path', ''),
                'return_code': result.get('returnCode', -1),
                'num_messages': len(result.get('messages', [])),
                'num_tactics': len(tacticStates),
                'response': result,
                'used_actual_source': theoremSource is not None,
                'source_code': leanCode
            }
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}',
                'fetch_time': fetchTime,
                'api_latency': apiLatency,
                'full_name': fullName,
                'file_path': theoremData.get('file_path', ''),
                'num_tactics': len(tacticStates),
                'used_actual_source': theoremSource is not None,
                'source_code': leanCode
            }
    
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': 'Request timeout',
            'fetch_time': fetchTime,
            'api_latency': 35.0,
            'full_name': fullName,
            'file_path': theoremData.get('file_path', ''),
            'num_tactics': len(tacticStates),
            'used_actual_source': theoremSource is not None,
            'source_code': leanCode
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'fetch_time': fetchTime,
            'api_latency': 0,
            'full_name': fullName,
            'file_path': theoremData.get('file_path', ''),
            'num_tactics': len(tacticStates),
            'used_actual_source': theoremSource is not None,
            'source_code': leanCode
        }

def plotResponseTimes(results: List[Dict[str, Any]], timestamp: str):
    successfulResults = [r for r in results if r.get('success', False)]
    
    if not successfulResults:
        print("No successful results to plot")
        return
    
    fetchTimes = [r.get('fetch_time', 0) for r in successfulResults]
    apiLatencies = [r.get('api_latency', 0) for r in successfulResults]
    apiProcessingTimes = [r.get('api_processing_time', 0) for r in successfulResults]
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Lean 4 Verification API - Timing Analysis', fontsize=16, fontweight='bold')
    
    axes[0, 0].hist(apiLatencies, bins=50, color='steelblue', edgecolor='black', alpha=0.7)
    axes[0, 0].set_xlabel('API Latency (seconds)')
    axes[0, 0].set_ylabel('Frequency')
    axes[0, 0].set_title('Distribution of API Latency (Network + Processing)')
    axes[0, 0].axvline(np.mean(apiLatencies), color='red', linestyle='--', label=f'Mean: {np.mean(apiLatencies):.3f}s')
    axes[0, 0].axvline(np.median(apiLatencies), color='green', linestyle='--', label=f'Median: {np.median(apiLatencies):.3f}s')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    axes[0, 1].hist(apiProcessingTimes, bins=50, color='coral', edgecolor='black', alpha=0.7)
    axes[0, 1].set_xlabel('API Processing Time (seconds)')
    axes[0, 1].set_ylabel('Frequency')
    axes[0, 1].set_title('Distribution of Lean Verification Time')
    axes[0, 1].axvline(np.mean(apiProcessingTimes), color='red', linestyle='--', label=f'Mean: {np.mean(apiProcessingTimes):.3f}s')
    axes[0, 1].axvline(np.median(apiProcessingTimes), color='green', linestyle='--', label=f'Median: {np.median(apiProcessingTimes):.3f}s')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    
    axes[1, 0].scatter(range(len(apiLatencies)), apiLatencies, alpha=0.5, s=10, color='steelblue', label='API Latency')
    axes[1, 0].scatter(range(len(apiProcessingTimes)), apiProcessingTimes, alpha=0.5, s=10, color='coral', label='API Processing')
    axes[1, 0].set_xlabel('Theorem Index')
    axes[1, 0].set_ylabel('Time (seconds)')
    axes[1, 0].set_title('Timing Over Test Sequence')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)
    
    boxData = [fetchTimes, apiLatencies, apiProcessingTimes]
    axes[1, 1].boxplot(boxData, labels=['Fetch', 'API Latency', 'API Processing'], patch_artist=True)
    axes[1, 1].set_ylabel('Time (seconds)')
    axes[1, 1].set_title('Timing Comparison')
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    plotFile = f"benchmark_plot_{timestamp}.png"
    plt.savefig(plotFile, dpi=300, bbox_inches='tight')
    print(f"Plot saved to: {plotFile}")
    
    try:
        plt.show()
    except:
        pass

def runBenchmark():
    print(f"Loading benchmark data from val.json...")
    theorems = loadBenchmarkData('val.json', limit=BENCHMARK_SIZE)
    print(f"Loaded {len(theorems)} theorems")
    
    theoremsWithTactics = [t for t in theorems if len(t.get('traced_tactics', [])) > 0]
    theoremsWithoutTactics = [t for t in theorems if len(t.get('traced_tactics', [])) == 0]
    
    print(f"  - With tactics: {len(theoremsWithTactics)}")
    print(f"  - Without tactics (likely term-mode proofs): {len(theoremsWithoutTactics)}")
    
    print(f"\nStarting benchmark at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing {len(theorems)} theorems against API at {API_URL}\n")
    
    results = []
    successCount = 0
    verifiedCount = 0
    totalFetchTime = 0
    totalApiLatency = 0
    totalApiProcessingTime = 0
    skippedCount = 0
    actualSourceCount = 0
    
    for i, theorem in enumerate(theorems, 1):
        theoremData = extractProofState(theorem)
        
        print(f"[{i}/{len(theorems)}] Testing {theoremData['full_name'][:60]}...", end=' ', flush=True)
        
        result = verifyTheorem(theoremData)
        results.append(result)
        
        if result['success']:
            successCount += 1
            totalFetchTime += result.get('fetch_time', 0)
            totalApiLatency += result.get('api_latency', 0)
            totalApiProcessingTime += result.get('api_processing_time', 0)
            
            if result.get('used_actual_source', False):
                actualSourceCount += 1
            
            if result.get('verified', False):
                verifiedCount += 1
                status = '✓'
            else:
                status = '✗'
            
            sourceIndicator = '[REAL]' if result.get('used_actual_source', False) else '[MOCK]'
            fetchInfo = f"fetch:{result.get('fetch_time', 0):.2f}s"
            apiInfo = f"api:{result.get('api_latency', 0):.2f}s"
            print(f"{status} {sourceIndicator} ({fetchInfo}, {apiInfo})")
        else:
            print(f"ERROR: {result['error']}")
        
        if i % 10 == 0:
            print(f"\nProgress: {i}/{len(theorems)} - Success rate: {successCount}/{i} ({100*successCount/i:.1f}%)\n")
    
    print(f"\n{'='*80}")
    print("BENCHMARK RESULTS")
    print(f"{'='*80}")
    print(f"Total theorems tested: {len(theorems)}")
    print(f"  - With tactics: {len(theoremsWithTactics)}")
    print(f"  - Without tactics: {len(theoremsWithoutTactics)}")
    print(f"\nSuccessfully processed: {successCount} ({100*successCount/len(theorems):.1f}%)")
    print(f"  - Using actual source: {actualSourceCount} ({100*actualSourceCount/successCount if successCount > 0 else 0:.1f}%)")
    print(f"  - Using mock proof: {successCount - actualSourceCount}")
    print(f"Verified proofs: {verifiedCount} ({100*verifiedCount/len(theorems) if len(theorems) > 0 else 0:.1f}%)")
    print(f"Failed to process: {len(theorems) - successCount}")
    
    if successCount > 0:
        print(f"\nTiming Statistics:")
        print(f"  Total fetch time: {totalFetchTime:.2f}s")
        print(f"  Total API latency: {totalApiLatency:.2f}s")
        print(f"  Total API processing: {totalApiProcessingTime:.2f}s")
        print(f"\n  Average fetch time: {totalFetchTime/successCount:.3f}s")
        print(f"  Average API latency: {totalApiLatency/successCount:.3f}s")
        print(f"  Average API processing: {totalApiProcessingTime/successCount:.3f}s")
        
        fetchTimes = [r.get('fetch_time', 0) for r in results if r['success']]
        apiLatencies = [r.get('api_latency', 0) for r in results if r['success']]
        if apiLatencies:
            print(f"\n  Min API latency: {min(apiLatencies):.3f}s")
            print(f"  Max API latency: {max(apiLatencies):.3f}s")
    
    errors = [r for r in results if not r['success']]
    if errors:
        print(f"\nError Summary:")
        errorTypes = {}
        for error in errors:
            errorType = error['error']
            errorTypes[errorType] = errorTypes.get(errorType, 0) + 1
        
        for errorType, count in sorted(errorTypes.items(), key=lambda x: x[1], reverse=True):
            print(f"  {errorType}: {count}")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    sourcesFile = f"benchmark_sources_{timestamp}.json"
    with open(sourcesFile, 'w', encoding='utf-8') as f:
        sources = {}
        for result in results:
            if result.get('used_actual_source', False):
                sources[result['full_name']] = {
                    'source_code': result.get('source_code', ''),
                    'file_path': result.get('file_path', ''),
                    'verified': result.get('verified', False),
                    'num_tactics': result.get('num_tactics', 0)
                }
        json.dump(sources, f, indent=2)
    
    print(f"Source code saved to: {sourcesFile}")
    
    outputFile = f"benchmark_results_{timestamp}.json"
    with open(outputFile, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_theorems': len(theorems),
            'theorems_with_tactics': len(theoremsWithTactics),
            'theorems_without_tactics': len(theoremsWithoutTactics),
            'successful': successCount,
            'actual_source_count': actualSourceCount,
            'mock_proof_count': successCount - actualSourceCount,
            'verified': verifiedCount,
            'failed': len(theorems) - successCount,
            'total_fetch_time': totalFetchTime,
            'total_api_latency': totalApiLatency,
            'total_api_processing_time': totalApiProcessingTime,
            'average_fetch_time': totalFetchTime/successCount if successCount > 0 else 0,
            'average_api_latency': totalApiLatency/successCount if successCount > 0 else 0,
            'average_api_processing_time': totalApiProcessingTime/successCount if successCount > 0 else 0,
            'source_file': sourcesFile,
            'results': results
        }, f, indent=2)
    
    print(f"\nDetailed results saved to: {outputFile}")
    
    csvFile = f"benchmark_results_{timestamp}.csv"
    with open(csvFile, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'full_name', 'success', 'verified', 'fetch_time', 'api_latency',
            'api_processing_time', 'num_tactics', 'num_messages', 
            'return_code', 'error', 'used_actual_source'
        ])
        writer.writeheader()
        
        for result in results:
            writer.writerow({
                'full_name': result.get('full_name', ''),
                'success': result.get('success', False),
                'verified': result.get('verified', False),
                'fetch_time': result.get('fetch_time', 0),
                'api_latency': result.get('api_latency', 0),
                'api_processing_time': result.get('api_processing_time', 0),
                'num_tactics': result.get('num_tactics', 0),
                'num_messages': result.get('num_messages', 0),
                'return_code': result.get('return_code', -1),
                'error': result.get('error', ''),
                'used_actual_source': result.get('used_actual_source', False)
            })
    
    print(f"CSV results saved to: {csvFile}")
    
    if successCount > 0:
        plotResponseTimes(results, timestamp)
    
    print(f"{'='*80}")

if __name__ == '__main__':
    print("Lean 4 Verification API Benchmark")
    print(f"{'='*80}\n")
    
    try:
        response = requests.get('http://localhost:5000/health', timeout=5)
        if response.status_code == 200:
            print("✓ API is healthy and ready\n")
        else:
            print("⚠ API responded but may not be healthy\n")
    except Exception as e:
        print(f"✗ Cannot connect to API: {e}")
        print("Make sure the API is running on http://localhost:5000\n")
        exit(1)
    
    runBenchmark()
