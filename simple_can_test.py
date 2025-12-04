"""
Simple CAN Communication Test
Tests the enhanced code generation system with a basic CAN setup.
"""

# This is a simple test case document
# Use this in the Streamlit app as your input:

TEST_REQUEST = """
Create a CAN communication setup with the following:
- CAN cluster named 'Vehicle_CAN' at 500 kbps
- CAN channel named 'CAN_Channel_1'
- One CAN frame named 'SpeedFrame' with DLC 8 bytes and CAN ID 0x100
- One signal named 'VehicleSpeed' (16 bits, unsigned) inside the frame
- Map the signal to the PDU
- Save to 'simple_can_test.arxml'
"""

print("=" * 60)
print("SIMPLE CAN COMMUNICATION TEST")
print("=" * 60)
print("\nInstructions:")
print("1. Open the Streamlit app (http://localhost:8501)")
print("2. Copy the request below into the chat:")
print("\n" + "-" * 60)
print(TEST_REQUEST.strip())
print("-" * 60)
print("\n3. Wait for the system to generate and execute")
print("4. Check if 'simple_can_test.arxml' is created")
print("\nExpected Result:")
print("✅ Code generated with deep thinking")
print("✅ Script executes successfully")
print("✅ ARXML file created and valid")
print("✅ UI shows success message")
