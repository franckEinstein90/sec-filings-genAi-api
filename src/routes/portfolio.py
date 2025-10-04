from flask import Blueprint, request, jsonify

import os
import json

portfolio_bp = Blueprint('portfolio', __name__)
@portfolio_bp.route('', methods=['GET'])
def list_holdings():
    try:
        test = "test"
        return jsonify({'holdings': test}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

