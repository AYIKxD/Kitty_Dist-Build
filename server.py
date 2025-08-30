from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, db
import os

app = Flask(__name__)

# Initialize Firebase
cred = credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://kitty-dist-default-rtdb.firebaseio.com/'
})

# Get a reference to the root of the database
ref = db.reference('solutions')

@app.route('/solution/<question_id>', methods=['GET'])
def get_solution(question_id):
    """Get solution for a specific question from Firebase"""
    try:
        solution = ref.child(question_id).get()
        if solution:
            return jsonify({'solution': solution})
        else:
            # Backward compatibility check
            all_solutions = ref.get()
            if all_solutions:
                for key, sol_data in all_solutions.items():
                    if key.endswith('/' + question_id):
                        return jsonify({'solution': sol_data})
            return jsonify({'error': 'Solution not found'}), 404
    except Exception as e:
        print(f"Error getting solution: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/add/solution', methods=['POST'])
def add_solution():
    """Add a new solution to Firebase"""
    try:
        data = request.get_json()
        if not data or 'id' not in data or 'solution' not in data:
            return jsonify({"error": "Invalid data"}), 400
        
        question_id = data['id']
        solution_data = data['solution']
        
        ref.child(question_id).set(solution_data)
        
        return jsonify({"status": "success", "message": "Solution saved"})
    except Exception as e:
        print(f"Error adding solution: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

# This part is for local testing and will not be used by Deta
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 80)))
