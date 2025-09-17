import streamlit as st
from fact_checker import WikipediaFactChecker

# Set up the webpage
st.set_page_config(page_title="Wikipedia Fact-Checker", page_icon="🔍")
st.title("🔍 Wikipedia Fact-Checker Agent")
st.write("Enter a claim to verify using Wikipedia")

# Create a text input for the user
claim = st.text_input("Claim to fact-check:", placeholder="e.g., The first marathon runner died after finishing")

# When the user enters a claim
if claim:
    st.write(f"**Fact-checking:** '{claim}'")

    # Show a spinner while working
    with st.spinner("Researching on Wikipedia..."):
        fact_checker = WikipediaFactChecker()
        results = fact_checker.search_wikipedia(claim)

        if not results:
            st.warning("No relevant Wikipedia articles found.")
        else:
            evidence = []
            sources = []

            for result in results[:2]:
                content = fact_checker.get_page_content(result['pageid'])
                if content:
                    relevant_sentences = fact_checker.extract_relevant_sentences(content, claim)
                    evidence.extend(relevant_sentences)
                    sources.append({
                        "title": result["title"],
                        "url": f"https://en.wikipedia.org/?curid={result['pageid']}"
                    })

            verdict, relevant_evidence = fact_checker.analyze_evidence(evidence, claim)

            st.subheader(f"Verdict: {verdict}")

            if relevant_evidence:
                st.write("**Key Evidence:**")
                for i, evidence_text in enumerate(relevant_evidence[:3], 1):
                    st.write(f"{i}. {evidence_text[:200]}...")

            st.write("**Sources:**")
            for i, source in enumerate(sources, 1):
                st.write(f"{i}. [{source['title']}]({source['url']})")