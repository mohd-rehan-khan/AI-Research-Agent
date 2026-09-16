from flask import Flask, render_template, request, jsonify
import research_agent

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/research", methods=["POST"])
def research():
    data = request.get_json()
    question = data.get("question", "").strip()

    if not question:
        return jsonify({
            "success": False,
            "error": "Please enter a research question."
        }), 400

    try:
        result = research_agent.run_research(question)

        return jsonify({
            "success": True,
            "answer": result["answer"],
            "sources": result["sources"],
            "steps": result["steps"],
            "notes": result["notes"],
            "errors": result["errors"]
        })

    except Exception as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)